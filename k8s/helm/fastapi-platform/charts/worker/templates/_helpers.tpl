{{- define "worker.fullname" -}}
{{- default .Chart.Name .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "worker.selectorLabels" -}}
app: {{ include "worker.fullname" . }}
app.kubernetes.io/name: {{ include "worker.fullname" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{- define "worker.labels" -}}
{{ include "worker.selectorLabels" . }}
app.kubernetes.io/part-of: restaurant
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version }}
{{- end -}}

{{- define "worker.syncWave" -}}
{{- $waves := (.Values.global).syncWaves | default dict -}}
{{- with $waves }}
argocd.argoproj.io/sync-wave: {{ index . "app" | default "0" | quote }}
{{- end }}
{{- end -}}
