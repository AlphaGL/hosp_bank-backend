from django import forms
from .models import Payment
from patients.models import Visit


class PaymentCreateForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ['visit', 'notes']
        widgets = {
            'visit': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only visits with no existing payment AND that have services attached
        self.fields['visit'].queryset = (
            Visit.objects
            .filter(payment__isnull=True, visit_services__isnull=False)
            .distinct()
            .select_related('patient')
        )
        # Show "Patient Name — Visit #N (date)" instead of a raw ID
        self.fields['visit'].label_from_instance = lambda v: (
            f"{v.patient.full_name} — Visit #{v.pk} ({v.visit_date})"
        )

    def clean_visit(self):
        visit = self.cleaned_data['visit']
        return visit


class PaymentConfirmForm(forms.Form):
    amount_paid = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=0,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
    )
    payment_method = forms.ChoiceField(
        choices=Payment.METHOD_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    transaction_ref = forms.CharField(
        required=False,
        max_length=100,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
    )

    def clean_amount_paid(self):
        amount = self.cleaned_data.get('amount_paid')
        if amount is not None and amount <= 0:
            raise forms.ValidationError("Amount paid must be greater than zero.")
        return amount


class PaymentFilterForm(forms.Form):
    STATUS_CHOICES_BLANK = [('', 'All Statuses')] + Payment.STATUS_CHOICES

    status = forms.ChoiceField(
        choices=STATUS_CHOICES_BLANK,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'}),
    )
    date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control form-control-sm', 'type': 'date'}),
    )
    patient = forms.CharField(
        required=False,
        max_length=50,
        label='Patient ID',
        widget=forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'Patient ID'}),
    )