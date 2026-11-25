{{- define "api.fullname" -}}
{{- default .Chart.Name .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "api.selectorLabels" -}}
app: {{ include "api.fullname" . }}
app.kubernetes.io/name: {{ include "api.fullname" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{- define "api.labels" -}}
{{ include "api.selectorLabels" . }}
app.kubernetes.io/part-of: restaurant
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version }}
{{- end -}}

{{- define "api.syncWave" -}}
{{- $waves := (.Values.global).syncWaves | default dict -}}
{{- with $waves }}
argocd.argoproj.io/sync-wave: {{ index . "app" | default "0" | quote }}
{{- end }}
{{- end -}}
