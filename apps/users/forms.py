from django import forms
from captcha.fields import CaptchaField


class RegistoCaptchaForm(forms.Form):
    """
    Formulário de registo com captcha.
    Validado no servidor ANTES de criar o utilizador.
    Campos alinhados com RegistoSerializer.
    """
    username  = forms.CharField(max_length=150)
    telefone  = forms.CharField(max_length=20, required=False)
    email     = forms.EmailField()
    password  = forms.CharField(widget=forms.PasswordInput)
    password2 = forms.CharField(widget=forms.PasswordInput)
    captcha   = CaptchaField(error_messages={
        'invalid': 'Código de verificação incorrecto. Tente novamente.',
        'required': 'Por favor introduza o código de verificação.',
    })

    def clean(self):
        cleaned = super().clean()
        pw1 = cleaned.get('password')
        pw2 = cleaned.get('password2')
        if pw1 and pw2 and pw1 != pw2:
            self.add_error('password2', 'As passwords não coincidem.')
        return cleaned
