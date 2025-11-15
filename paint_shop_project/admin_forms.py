from pathlib import Path

from django import forms
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _


class DatabaseBackupForm(forms.Form):
    """Настройки создания резервной копии."""

    DESTINATION_CHOICES = (
        ("default", _("Стандартное хранилище (MEDIA_ROOT/backups)")),
        ("custom", _("Собственная папка на сервере")),
    )

    destination = forms.ChoiceField(
        label=_("Куда сохранить"),
        choices=DESTINATION_CHOICES,
        widget=forms.RadioSelect,
        initial="default",
    )
    folder_name = forms.CharField(
        label=_("Название папки"),
        required=False,
        help_text=_("Будет создана вложенная папка с бэкапом (только буквы, цифры, дефисы и подчёркивания)."),
        widget=forms.TextInput(attrs={
            "class": "vTextField",
            "placeholder": _("например, nightly"),
        }),
    )
    custom_directory = forms.CharField(
        label=_("Путь до папки на сервере"),
        required=False,
        help_text=_("Абсолютный путь, в который будет создана подпапка с бэкапом."),
        widget=forms.TextInput(attrs={
            "class": "vTextField",
            "placeholder": _("C:/Backups/Postgres"),
        }),
    )

    def clean_folder_name(self):
        raw = self.cleaned_data.get("folder_name") or ""
        if not raw:
            return ""
        slug = slugify(raw).replace("-", "_")
        if not slug:
            raise forms.ValidationError(_("Укажите корректное название папки."))
        return slug

    def clean_custom_directory(self):
        destination = self.data.get("destination")
        path_value = self.cleaned_data.get("custom_directory")
        if destination == "custom":
            if not path_value:
                raise forms.ValidationError(_("Укажите путь к папке."))
            resolved = Path(path_value).expanduser().resolve()
            if not resolved.exists():
                raise forms.ValidationError(_("Папка не найдена: %s") % resolved)
            if not resolved.is_dir():
                raise forms.ValidationError(_("Укажите путь к каталогу, а не к файлу."))
            return str(resolved)
        return ""

    def clean(self):
        cleaned = super().clean()
        destination = cleaned.get("destination")
        if destination != "custom":
            cleaned["custom_directory"] = ""
        return cleaned


class DatabaseRestoreUploadForm(forms.Form):
    """Форма загрузки резервной копии для восстановления."""

    backup_file = forms.FileField(
        label="Файл резервной копии",
        help_text="Поддерживаются файлы, созданные pg_dump (.dump, .sql).",
        widget=forms.ClearableFileInput(attrs={
            "class": "vClearableFileInput",
            "accept": ".dump,.sql,.backup",
        }),
    )
    confirm = forms.BooleanField(
        label="Я подтверждаю, что текущие данные будут перезаписаны",
        required=True,
        widget=forms.CheckboxInput(attrs={"class": "checkboxinput"}),
    )


class DatabaseRestoreExistingForm(forms.Form):
    """Форма восстановления из уже созданного бэкапа."""

    backup_name = forms.ChoiceField(
        label="Доступные бэкапы",
        choices=(),
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    confirm = forms.BooleanField(
        label="Подтверждаю перезапись текущей базы",
        required=True,
        widget=forms.CheckboxInput(attrs={"class": "checkboxinput"}),
    )

    def __init__(self, *args, backup_choices=None, **kwargs):
        super().__init__(*args, **kwargs)
        choices = backup_choices or []
        if choices:
            self.fields["backup_name"].choices = choices
            self.fields["backup_name"].widget.attrs.pop("disabled", None)
        else:
            self.fields["backup_name"].choices = []
            self.fields["backup_name"].widget.attrs["disabled"] = "disabled"











