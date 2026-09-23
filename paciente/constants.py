VENTANA_MINUTOS = 15
ALERTA_CUIDADOR_MINUTOS = 20
# Push legacy: reintento tras la hora exacta
VENTANA_REINTENTO_ALARMA_MINUTOS = 10
# SMS: avisar entre 10 y 0 minutos antes de la hora programada (ideal ~5–10 min antes)
SMS_ANTICIPO_MAX_MINUTOS = 10
# Si el cron falló o llegó tarde, aún reintentar hasta N minutos después de la hora
SMS_REINTENTO_DESPUES_MINUTOS = 15
# Un SMS GSM-7 = 160 caracteres (sin tildes/ñ). UCS-2 con tildes baja a 70.
SMS_MAX_CARACTERES = 160
