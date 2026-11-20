{#- Falla con cada fila no nula fuera de [min_valor, max_valor].
    `inclusivo_min: false` exige valor > min_valor. -#}
{% test en_rango(model, column_name, min_valor=none, max_valor=none, inclusivo_min=true) %}
select {{ column_name }}
from {{ model }}
where {{ column_name }} is not null
  and (
    {% if min_valor is not none %}
      {{ column_name }} {{ '<' if inclusivo_min else '<=' }} {{ min_valor }}
    {% else %} false {% endif %}
    {% if max_valor is not none %}
      or {{ column_name }} > {{ max_valor }}
    {% endif %}
  )
{% endtest %}
