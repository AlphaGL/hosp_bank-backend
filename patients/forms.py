from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserChangeForm
from .models import Staff, Patient, Visit


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

class StaffLoginForm(AuthenticationForm):
    """
    Replaces LoginView / StaffSerializer auth logic.
    Extends Django's built-in AuthenticationForm — handles authenticate() for us.
    """
    username = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control', 'autofocus': True, 'placeholder': 'Username'})
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Password'})
    )


class StaffProfileForm(forms.ModelForm):
    """
    Replaces PATCH on StaffProfileView.
    Only editable personal fields; role/is_active guarded by admin views.
    """
    class Meta:
        model = Staff
        fields = ['first_name', 'last_name', 'email', 'phone', 'department']
        widgets = {
            'first_name':  forms.TextInput(attrs={'class': 'form-control'}),
            'last_name':   forms.TextInput(attrs={'class': 'form-control'}),
            'email':       forms.EmailInput(attrs={'class': 'form-control'}),
            'phone':       forms.TextInput(attrs={'class': 'form-control'}),
            'department':  forms.TextInput(attrs={'class': 'form-control'}),
        }


# ---------------------------------------------------------------------------
# Staff (admin-only)
# ---------------------------------------------------------------------------

class StaffCreateForm(forms.ModelForm):
    """
    Replaces StaffCreateSerializer — admin creates new staff accounts.
    """
    password = forms.CharField(
        min_length=6,
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
    )

    class Meta:
        model = Staff
        fields = ['username', 'first_name', 'last_name', 'email',
                  'role', 'phone', 'department']
        widgets = {f: forms.TextInput(attrs={'class': 'form-control'}) for f in
                   ['username', 'first_name', 'last_name', 'email', 'phone', 'department']}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['role'].widget.attrs['class'] = 'form-select'
        self.fields['email'].widget = forms.EmailInput(attrs={'class': 'form-control'})

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('password') != cleaned.get('confirm_password'):
            raise forms.ValidationError("Passwords do not match.")
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password'])
        if commit:
            user.save()
        return user


class StaffUpdateForm(forms.ModelForm):
    """Admin editing an existing staff member (role, active status, etc.)."""
    class Meta:
        model = Staff
        fields = ['first_name', 'last_name', 'email', 'role',
                  'phone', 'department', 'is_active']
        widgets = {
            'first_name':  forms.TextInput(attrs={'class': 'form-control'}),
            'last_name':   forms.TextInput(attrs={'class': 'form-control'}),
            'email':       forms.EmailInput(attrs={'class': 'form-control'}),
            'role':        forms.Select(attrs={'class': 'form-select'}),
            'phone':       forms.TextInput(attrs={'class': 'form-control'}),
            'department':  forms.TextInput(attrs={'class': 'form-control'}),
            'is_active':   forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


# ---------------------------------------------------------------------------
# Patient
# ---------------------------------------------------------------------------

class PatientForm(forms.ModelForm):
    """
    Replaces PatientSerializer for create & update.
    patient_id is auto-generated; registered_by set in the view.
    """
    class Meta:
        model = Patient
        fields = ['first_name', 'last_name', 'age', 'gender',
                  'phone', 'email', 'address']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name':  forms.TextInput(attrs={'class': 'form-control'}),
            'age':        forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'gender':     forms.Select(attrs={'class': 'form-select'}),
            'phone':      forms.TextInput(attrs={'class': 'form-control'}),
            'email':      forms.EmailInput(attrs={'class': 'form-control'}),
            'address':    forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class PatientSearchForm(forms.Form):
    """
    Replaces PatientViewSet.search_patient() custom action.
    Used on the patient list to filter results.
    """
    q = forms.CharField(
        required=False,
        label='Search',
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-sm',
            'placeholder': 'ID, name, or phone…',
        }),
    )


# ---------------------------------------------------------------------------
# Visit
# ---------------------------------------------------------------------------

class VisitCreateForm(forms.ModelForm):
    """
    Replaces VisitSerializer for creation.
    Status is set to AWAITING_PAYMENT in the view; not user-supplied.
    """
    class Meta:
        model = Visit
        fields = ['patient', 'priority', 'notes']
        widgets = {
            'patient':  forms.Select(attrs={'class': 'form-select'}),
            'priority': forms.Select(attrs={'class': 'form-select'}),
            'notes':    forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class VisitFilterForm(forms.Form):
    """
    Replaces inline get_queryset() filtering on VisitViewSet.
    """
    STATUS_BLANK = [('', 'All Statuses')] + Visit.STATUS_CHOICES
    PRIORITY_BLANK = [('', 'All Priorities')] + Visit.PRIORITY_CHOICES

    status = forms.ChoiceField(
        choices=STATUS_BLANK, required=False,
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'}),
    )
    priority = forms.ChoiceField(
        choices=PRIORITY_BLANK, required=False,
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'}),
    )
    date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control form-control-sm', 'type': 'date'}),
    )


class VisitStatusForm(forms.Form):
    """
    Replaces VisitViewSet.update_status() custom action.
    Minimal single-field form submitted from the visit detail page.
    """
    status = forms.ChoiceField(
        choices=Visit.STATUS_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )