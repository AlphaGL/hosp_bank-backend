from django import forms
from .models import DiagnosticService, VisitService


class DiagnosticServiceForm(forms.ModelForm):
    class Meta:
        model = DiagnosticService
        fields = [
            'name', 'code', 'category', 'description',
            'base_price', 'department', 'duration_minutes', 'is_active',
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }


class VisitServiceForm(forms.ModelForm):
    """Used when creating a new VisitService entry."""
    class Meta:
        model = VisitService
        fields = ['visit', 'service', 'notes']

    def save(self, commit=True):
        instance = super().save(commit=False)
        # price_at_booking is set automatically by the model's save()
        if commit:
            instance.save()
        return instance


class VisitServiceUpdateForm(forms.ModelForm):
    """Used for editing an existing VisitService (status, notes, report, staff)."""
    class Meta:
        model = VisitService
        fields = ['status', 'notes', 'report', 'attended_by', 'started_at', 'completed_at']
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 3}),
            'started_at': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'completed_at': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }