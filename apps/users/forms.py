from django import forms
from django.utils import timezone
from captcha.fields import CaptchaField

IDADE_MINIMA = 18


class RegistoCaptchaForm(forms.Form):
    """
    Formulário de registo com captcha.
    Validado no servidor ANTES de criar o utilizador.
    Campos alinhados com RegistoSerializer.
    """
    username = forms.CharField(max_length=150)
    telefone = forms.CharField(max_length=20, required=False)
    email = forms.EmailField()
    data_nascimento = forms.DateField(
        required=True,
        widget=forms.DateInput(attrs={'type': 'date'}),
        error_messages={'required': 'A data de nascimento é obrigatória.'},
    )
    password = forms.CharField(widget=forms.PasswordInput)
    password2 = forms.CharField(widget=forms.PasswordInput)
    captcha = CaptchaField(error_messages={
        'invalid': 'Código de verificação incorrecto. Tente novamente.',
        'required': 'Por favor introduza o código de verificação.',
    })

    def clean_data_nascimento(self):
        nascimento = self.cleaned_data.get('data_nascimento')
        if nascimento is None:
            raise forms.ValidationError('A data de nascimento é obrigatória.')
        hoje = timezone.localdate()
        aniversario_este_ano = nascimento.replace(year=hoje.year)
        idade = hoje.year - nascimento.year
        if aniversario_este_ano > hoje:
            idade -= 1
        if idade < IDADE_MINIMA:
            raise forms.ValidationError(
                f'É necessário ter pelo menos {IDADE_MINIMA} anos para se registar.'
            )
        return nascimento

    def clean(self):
        cleaned = super().clean()
        pw1 = cleaned.get('password')
        pw2 = cleaned.get('password2')
        if pw1 and pw2 and pw1 != pw2:
            self.add_error('password2', 'As passwords não coincidem.')
        return cleaned
