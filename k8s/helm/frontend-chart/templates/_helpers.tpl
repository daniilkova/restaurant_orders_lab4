{{/* Имя ресурсов: frontend (или fullnameOverride) */}}
{{- define "frontend.fullname" -}}
{{- default "frontend" .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "frontend.labels" -}}
app: frontend
app.kubernetes.io/name: frontend
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/part-of: restaurant
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version }}
{{- end -}}

{{/* Селектор: track отличает стабильную версию от canary */}}
{{- define "frontend.selectorLabels" -}}
app: frontend
track: {{ .track }}
{{- end -}}

{{/* Общая спецификация пода (stable и canary отличаются только тегом и меткой track) */}}
{{- define "frontend.podSpec" -}}
automountServiceAccountToken: false
securityContext:
  runAsNonRoot: true
  runAsUser: 101
  runAsGroup: 101
  fsGroup: 101
  seccompProfile:
    type: RuntimeDefault
containers:
  - name: frontend
    image: "{{ .root.Values.image.repository }}:{{ .tag }}"
    imagePullPolicy: {{ .root.Values.image.pullPolicy }}
    ports:
      - name: http
        containerPort: {{ .root.Values.containerPort }}
    securityContext:
      allowPrivilegeEscalation: false
      readOnlyRootFilesystem: true
      capabilities:
        drop: ["ALL"]
    readinessProbe:
      httpGet:
        path: /healthz
        port: http
      periodSeconds: 10
    livenessProbe:
      httpGet:
        path: /healthz
        port: http
      periodSeconds: 20
    resources:
      {{- toYaml .root.Values.resources | nindent 6 }}
    volumeMounts:
      - name: tmp
        mountPath: /tmp
volumes:
  - name: tmp
    emptyDir: {}
{{- end -}}

{{- define "frontend.tls" -}}
{{- if .Values.ingress.tls.enabled }}
tls:
  - hosts:
      - {{ .Values.ingress.host }}
    secretName: {{ .Values.ingress.tls.secretName }}
{{- end }}
{{- end -}}
