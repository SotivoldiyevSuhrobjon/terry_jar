import json
import secrets

from django import forms
from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import UserChangeForm
from django.contrib.auth.models import Group
from django.utils.html import format_html

from . import sync
from .models import AuditLog, Record, SyncOp, User
from .roles import PERMS, ROLE_DEF, VIEW_PERMS


def branch_choices():
    rows = Record.objects.filter(col="branches", deleted=False).values_list("data", flat=True)
    ch = [("*", "Barcha filiallar")]
    ch += [(d.get("id"), d.get("name") or d.get("id")) for d in rows if isinstance(d, dict) and d.get("id")]
    if len(ch) == 1:
        ch.append(("jar", "Jar"))
    return ch


class StaffMixin(forms.Form):
    perms = forms.MultipleChoiceField(label="Ruxsatlar", choices=PERMS, required=False,
                                      widget=forms.CheckboxSelectMultiple,
                                      help_text="Bo'sh qoldirilsa — lavozimning standart ruxsatlari beriladi.")
    branch = forms.ChoiceField(label="Filial", choices=())

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.fields["branch"].choices = branch_choices()

    def clean(self):
        data = super().clean()
        role = data.get("role")
        if role and not data.get("perms"):
            data["perms"] = VIEW_PERMS if data.get("readonly") else list(ROLE_DEF.get(role, []))
        if data.get("readonly"):
            data["perms"] = [p for p in data["perms"] if p in VIEW_PERMS]
        if role == "director":
            data["branch"] = "*"
        return data


class StaffForm(StaffMixin, UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = User
        fields = "__all__"


class StaffCreateForm(StaffMixin, forms.ModelForm):
    password = forms.CharField(label="Vaqtinchalik parol", required=False,
                               help_text="Bo'sh qoldirilsa avtomatik yaratiladi. Xodim birinchi kirishda o'zgartiradi.")

    class Meta:
        model = User
        fields = ("username", "full_name", "role", "branch", "smena", "readonly", "perms")


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    form = StaffForm
    add_form = StaffCreateForm
    list_display = ("full_name", "username", "role", "branch", "smena", "readonly", "is_active", "last_login")
    list_filter = ("role", "branch", "smena", "readonly", "is_active")
    search_fields = ("full_name", "username")
    ordering = ("role", "full_name")
    readonly_fields = ("rid", "last_login", "date_joined")
    actions = ["reset_password", "block", "unblock"]
    fieldsets = (
        ("Xodim", {"fields": ("full_name", "username", "password", "rid")}),
        ("Lavozim va filial", {"fields": ("role", "branch", "smena", "readonly", "perms")}),
        ("Holat", {"fields": ("is_active", "must_change_password", "is_staff", "is_superuser")}),
        ("Vaqt", {"fields": ("last_login", "date_joined"), "classes": ("collapse",)}),
    )
    add_fieldsets = (("Yangi xodim", {"fields": ("full_name", "username", "password", "role", "branch", "smena",
                                                  "readonly", "perms")}),)
    filter_horizontal = ()

    def has_delete_permission(self, request, obj=None):
        return False  # xodim o'chirilmaydi — bloklanadi (tarix va audit buzilmasligi uchun)

    def save_model(self, request, obj, form, change):
        temp = None
        if not change:
            temp = form.cleaned_data.get("password") or secrets.token_urlsafe(6)
            obj.set_password(temp)
            obj.must_change_password = True
        obj.perms = form.cleaned_data.get("perms", obj.perms)
        super().save_model(request, obj, form, change)
        sync.sync_user_record(obj, by=request.user)
        if temp:
            messages.warning(request, format_html("{} uchun vaqtinchalik parol: <b>{}</b> — xodimga bering.",
                                                  obj.full_name, temp))

    @admin.action(description="Parolni tiklash (vaqtinchalik parol yaratish)")
    def reset_password(self, request, qs):
        for u in qs:
            temp = secrets.token_urlsafe(6)
            u.set_password(temp)
            u.must_change_password = True
            u.save()
            messages.warning(request, format_html("{} ({}): <b>{}</b>", u.full_name, u.username, temp))

    @admin.action(description="Bloklash (tizimga kira olmaydi)")
    def block(self, request, qs):
        for u in qs.exclude(pk=request.user.pk):
            u.is_active = False
            u.save(update_fields=["is_active"])
            sync.sync_user_record(u, by=request.user)

    @admin.action(description="Blokdan chiqarish")
    def unblock(self, request, qs):
        for u in qs:
            u.is_active = True
            u.save(update_fields=["is_active"])
            sync.sync_user_record(u, by=request.user)


class ReadOnlyAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


def _pretty(v):
    return format_html("<pre style='white-space:pre-wrap;max-width:900px'>{}</pre>",
                       json.dumps(v, ensure_ascii=False, indent=2))


@admin.register(Record)
class RecordAdmin(ReadOnlyAdmin):
    list_display = ("col", "rid", "short", "rev", "deleted", "updated_by", "updated_at")
    list_filter = ("col", "deleted")
    search_fields = ("rid",)
    readonly_fields = ("col", "rid", "kind", "pretty", "rev", "seq", "deleted", "updated_by", "updated_at")
    exclude = ("data",)

    @admin.display(description="Ma'lumot")
    def short(self, obj):
        s = json.dumps(obj.data, ensure_ascii=False)
        return s[:120] + ("…" if len(s) > 120 else "")

    @admin.display(description="To'liq ma'lumot")
    def pretty(self, obj):
        return _pretty(obj.data)


@admin.register(AuditLog)
class AuditLogAdmin(ReadOnlyAdmin):
    list_display = ("ts", "username", "action", "col", "rid", "note", "ip")
    list_filter = ("action", "col", "username")
    search_fields = ("rid", "username", "note")
    date_hierarchy = "ts"
    readonly_fields = ("ts", "user", "username", "action", "col", "rid", "note", "ip", "before_p", "after_p")
    exclude = ("before", "after")

    @admin.display(description="Oldin")
    def before_p(self, obj):
        return _pretty(obj.before)

    @admin.display(description="Keyin")
    def after_p(self, obj):
        return _pretty(obj.after)


@admin.register(SyncOp)
class SyncOpAdmin(ReadOnlyAdmin):
    list_display = ("op_id", "user", "rev", "created")
    list_filter = ("user",)


admin.site.unregister(Group)
