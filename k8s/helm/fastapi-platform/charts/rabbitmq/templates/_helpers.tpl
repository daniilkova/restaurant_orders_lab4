{{- define "rabbitmq.fullname" -}}
{{- default .Chart.Name .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "rabbitmq.selectorLabels" -}}
app: {{ include "rabbitmq.fullname" . }}
app.kubernetes.io/name: {{ include "rabbitmq.fullname" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{- define "rabbitmq.labels" -}}
{{ include "rabbitmq.selectorLabels" . }}
app.kubernetes.io/part-of: restaurant
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version }}
{{- end -}}

{{- define "rabbitmq.syncWave" -}}
{{- $waves := (.Values.global).syncWaves | default dict -}}
{{- with $waves }}
argocd.argoproj.io/sync-wave: {{ index . "infra" | default "0" | quote }}
{{- end }}
{{- end -}}
