{{/* vim: set filetype=mustache: */}}
{{/*
Expand the name of the chart.
*/}}
{{- define "k8s-backup-manager.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "k8s-backup-manager.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "k8s-backup-manager.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "k8s-backup-manager.labels" -}}
helm.sh/chart: {{ include "k8s-backup-manager.chart" . }}
{{ include "k8s-backup-manager.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "k8s-backup-manager.selectorLabels" -}}
app.kubernetes.io/name: {{ include "k8s-backup-manager.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "k8s-backup-manager.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "k8s-backup-manager.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Pod 规格模板
*/}}
{{- define "k8s-backup-manager.podSpec" -}}
serviceAccountName: {{ include "k8s-backup-manager.serviceAccountName" . }}
{{- with .Values.rbac.automountServiceAccountToken }}
automountServiceAccountToken: {{ . }}
{{- end }}
{{- with .Values.podSecurityContext }}
securityContext:
  {{- toYaml . | nindent 2 }}
{{- end }}
containers:
  - name: backup-manager
    image: "{{ .Values.image.repository }}:{{ .Values.image.tag | default .Chart.AppVersion }}"
    imagePullPolicy: {{ .Values.image.pullPolicy }}
    command:
      - python
      - src/main.py
    args:
      {{- if eq .Values.backupManager.mode "discover" }}
      - discover
      {{- else if eq .Values.backupManager.mode "generate" }}
      - generate
      - --output
      - {{ .Values.backupManager.outputDir }}
      {{- end }}
      {{- range .Values.backupManager.namespaces }}
      - --namespace
      - {{ . }}
      {{- end }}
    {{- if .Values.env }}
    env:
      {{- toYaml .Values.env | nindent 6 }}
    {{- end }}
    {{- if .Values.envFrom }}
    envFrom:
      {{- toYaml .Values.envFrom | nindent 6 }}
    {{- end }}
    volumeMounts:
      - name: config
        mountPath: /app/config.yaml
        subPath: config.yaml
        readOnly: true
      {{- if .Values.backupStorage.enabled }}
      - name: backup-storage
        mountPath: {{ .Values.backupManager.outputDir }}
      {{- end }}
      {{- if .Values.backupScripts.enabled }}
      - name: scripts
        mountPath: /app/scripts
        readOnly: true
      {{- end }}
      {{- if .Values.extraVolumeMounts }}
      {{- toYaml .Values.extraVolumeMounts | nindent 6 }}
      {{- end }}
    {{- with .Values.resources }}
    resources:
      {{- toYaml . | nindent 6 }}
    {{- end }}
    {{- with .Values.securityContext }}
    securityContext:
      {{- toYaml . | nindent 6 }}
    {{- end }}
{{- if .Values.image.pullSecrets }}
imagePullSecrets:
  {{- toYaml .Values.image.pullSecrets | nindent 2 }}
{{- end }}
{{- with .Values.nodeSelector }}
nodeSelector:
  {{- toYaml . | nindent 2 }}
{{- end }}
{{- with .Values.affinity }}
affinity:
  {{- toYaml . | nindent 2 }}
{{- end }}
{{- with .Values.tolerations }}
tolerations:
  {{- toYaml . | nindent 2 }}
{{- end }}
volumes:
  - name: config
    configMap:
      name: {{ include "k8s-backup-manager.fullname" . }}-config
  {{- if .Values.backupStorage.enabled }}
  - name: backup-storage
    persistentVolumeClaim:
      claimName: {{ include "k8s-backup-manager.fullname" . }}-backup
  {{- end }}
  {{- if .Values.backupScripts.enabled }}
  - name: scripts
    configMap:
      name: {{ include "k8s-backup-manager.fullname" . }}-scripts
  {{- end }}
  {{- if .Values.extraVolumes }}
  {{- toYaml .Values.extraVolumes | nindent 2 }}
  {{- end }}
{{- end }}
