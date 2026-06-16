import django_filters
from django.db.models import Q
from .models import Anuncio


class AnuncioFilter(django_filters.FilterSet):
    preco_min = django_filters.NumberFilter(field_name='preco', lookup_expr='gte')
    preco_max = django_filters.NumberFilter(field_name='preco', lookup_expr='lte')
    categoria = django_filters.CharFilter(method='filter_categoria')
    provincia = django_filters.CharFilter(lookup_expr='iexact')
    cidade = django_filters.CharFilter(lookup_expr='iexact')
    condicao = django_filters.CharFilter(lookup_expr='iexact')

    class Meta:
        model = Anuncio
        fields = ['categoria', 'provincia', 'cidade',
                  'condicao', 'preco_min', 'preco_max']

    def filter_categoria(self, queryset, name, value):
        """Aceita slug de categoria-pai ou subcategoria."""
        return queryset.filter(
            Q(categoria__slug=value) | Q(categoria__pai__slug=value)
        )