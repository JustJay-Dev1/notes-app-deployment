Build your Helm chart(s) here. See `ASSIGNMENT.md` (Part 2) for requirements.

Expected structure (adjust as you see fit):

```
helm/
  notes-api/
    Chart.yaml
    values.yaml
    values-dev.yaml
    values-prod.yaml
    charts/            # dependency chart(s), e.g. postgresql, land here after `helm dependency build`
    templates/
      deployment.yaml
      service.yaml
      configmap.yaml
      secret.yaml
      serviceaccount.yaml
      hpa.yaml          # optional
      ingress.yaml       # optional
      NOTES.txt
```
