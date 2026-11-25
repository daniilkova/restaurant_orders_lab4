{{/* Общие метки всех ресурсов платформы */}}
{{- define "platform.labels" -}}
app.kubernetes.io/part-of: restaurant
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/instance: {{ .Release.Name }}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end -}}

{{/* Аннотация Argo CD sync wave: include "platform.syncWave" (list . "infra") */}}
{{- define "platform.syncWave" -}}
argocd.argoproj.io/sync-wave: {{ index (index . 0).Values.global.syncWaves (index . 1) | quote }}
{{- end -}}

{{/* Хост PostgreSQL зависит от режима: свой StatefulSet или сервис -rw кластера CloudNativePG */}}
{{- define "platform.databaseHost" -}}
{{- if eq .Values.database.mode "cnpg" -}}
{{ printf "%s-rw" .Values.database.cnpg.clusterName }}
{{- else -}}
postgres
{{- end -}}
{{- end -}}

{{- define "platform.secretName" -}}
{{- default .Values.global.secretName .Values.secrets.existingSecret -}}
{{- end -}}
