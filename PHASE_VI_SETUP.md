# Phase VI: Global Scale & Hardening - Setup Guide

## Overview

Phase VI implements production-grade Kubernetes orchestration, comprehensive monitoring, CI/CD pipelines, security hardening, and disaster recovery for the Enhanced Autonomous Cognitive Galaxy v2.0 system. This phase enables global-scale deployment with high availability, auto-scaling, and comprehensive observability.

## Architecture

### Kubernetes Cluster Requirements

- **Kubernetes Version**: 1.22+ (1.25+ recommended)
- **Min Nodes**: 3 (for HA)
- **Min Resources**: 8 CPU cores, 16GB RAM per node
- **Container Runtime**: K3s, containerd, or Docker
- **Network Plugin**: Calico, Flannel, or Weave (with NetworkPolicy support)

### Components

| Component | Type | Replicas | Storage |
|-----------|------|----------|---------|
| PostgreSQL | StatefulSet | 1 | 50Gi PVC |
| Redis | StatefulSet | 1 | 10Gi PVC |
| Authority Chain | StatefulSet | 1 | 100Gi PVC |
| Swarm Nodes | StatefulSet | 2 | None |
| Edge Planet | Deployment | 3 | None |
| FL Aggregator | Deployment | 1 | 10Gi |
| Predictive Service | Deployment | 2 | None |
| Webhook Service | Deployment | 2 | None |
| Compliance Engine | Deployment | 2 | None |
| Dashboard | Deployment | 2 | None |
| Prometheus | StatefulSet | 1 | 50Gi PVC |
| Grafana | Deployment | 1 | None |

## Prerequisites

### Local Development

1. **Install kubectl**:
   ```bash
   # macOS
   brew install kubectl
   
   # Linux
   curl -LO "https://dl.k8s.io/release/v1.28.0/bin/linux/amd64/kubectl"
   chmod +x kubectl && sudo mv kubectl /usr/local/bin
   ```

2. **Install a Local Kubernetes Cluster**:
   ```bash
   # Option 1: Kind (recommended for development)
   brew install kind
   kind create cluster --config k8s/kind-config.yaml
   
   # Option 2: K3s (lightweight, production-like)
   curl -sfL https://get.k3s.io | sh -
   
   # Option 3: Minikube
   brew install minikube
   minikube start --cpus=4 --memory=8192
   ```

3. **Install Helm** (optional, for package management):
   ```bash
   brew install helm
   ```

4. **Install cert-manager** (for TLS certificates):
   ```bash
   kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.13.0/cert-manager.yaml
   ```

### Production Requirements

- Managed Kubernetes (EKS, GKE, AKS, or self-hosted K8s)
- LoadBalancer service support (or Ingress with HTTP controller)
- Persistent volume provisioner
- Container registry (ECR, GCR, ACR, or self-hosted)
- Monitoring backend (Prometheus, CloudWatch, etc.)

## Deployment Instructions

### 1. Prepare the Environment

```bash
# Create namespace
kubectl apply -f k8s/namespaces.yaml

# Create ConfigMaps with environment variables
kubectl apply -f k8s/configmaps.yaml

# Create Secrets (update with real values first!)
# Edit k8s/secrets.yaml.template with production values
# Then apply:
kubectl apply -f <(envsubst < k8s/secrets.yaml.template)
```

### 2. Deploy Storage

```bash
# PostgreSQL and Redis (includes PVCs)
kubectl apply -f k8s/deployments/postgres-redis.yaml

# Wait for PVCs to bind
kubectl -n galaxy wait --for=condition=Bound pvc/postgres-data --timeout=300s
kubectl -n galaxy wait --for=condition=Bound pvc/redis-data --timeout=300s

# Wait for pods to be ready
kubectl -n galaxy wait --for=condition=Ready pod/postgres-0 --timeout=300s
kubectl -n galaxy wait --for=condition=Ready pod/redis-0 --timeout=300s
```

### 3. Deploy Core Services

```bash
# Authority Chain (blockchain)
kubectl apply -f k8s/deployments/authority-chain.yaml
kubectl -n galaxy wait --for=condition=Ready pod -l app=authority-chain --timeout=300s

# Swarm Nodes (P2P network)
kubectl apply -f k8s/deployments/swarm-node.yaml
kubectl -n galaxy wait --for=condition=Ready pod -l app=swarm-node --timeout=300s
```

### 4. Deploy Application Services

```bash
# Intelligence Layer (Edge, FL)
kubectl apply -f k8s/deployments/intelligence-layer.yaml

# Expansion Layer (Webhook, Compliance, Predictive)
kubectl apply -f k8s/deployments/expansion-layer.yaml

# Dashboard Frontend
kubectl apply -f k8s/deployments/dashboard.yaml

# Wait for all to be ready
kubectl -n galaxy rollout status deployment
```

### 5. Deploy Services & Ingress

```bash
# Kubernetes Services
kubectl apply -f k8s/services/services.yaml

# Ingress (requires cert-manager)
kubectl apply -f k8s/ingress.yaml

# Check status
kubectl -n galaxy get svc
kubectl -n galaxy get ingress
```

### 6. Apply Network Policies

```bash
# Zero-trust security policies
kubectl apply -f k8s/network-policies.yaml

# Verify policies are applied
kubectl -n galaxy get networkpolicies
```

### 7. Deploy Monitoring Stack

```bash
# Prometheus and Grafana
kubectl apply -f k8s/monitoring/prometheus.yaml
kubectl apply -f k8s/monitoring/grafana.yaml

# Wait for monitoring to be ready
kubectl -n galaxy-monitoring rollout status deployment/grafana
kubectl -n galaxy-monitoring wait --for=condition=Ready pod -l app=prometheus --timeout=300s
```

## Verification

### Health Checks

```bash
# Check Pod Status
kubectl -n galaxy get pods -o wide

# Check Services
kubectl -n galaxy get svc

# Check PVCs
kubectl -n galaxy get pvc

# Check Events
kubectl -n galaxy get events --sort-by='.lastTimestamp'
```

### Service Connectivity

```bash
# Port forward to test
kubectl -n galaxy port-forward svc/authority-chain 1317:1317
curl http://localhost:1317/health

# Check DNS resolution
kubectl exec -it <pod-name> -- nslookup authority-chain.galaxy.svc.cluster.local
```

### Monitoring Access

```bash
# Access Grafana
kubectl -n galaxy-monitoring port-forward svc/grafana 3000:80
# Open http://localhost:3000 (admin/admin)

# Access Prometheus
kubernetes -n galaxy-monitoring port-forward svc/prometheus 9090:9090
# Open http://localhost:9090

# View metrics
curl http://localhost:9090/api/v1/labels
```

## Production Configuration

### 1. TLS Certificates

Update `k8s/ingress.yaml` with your domain:

```yaml
spec:
  tls:
  - hosts:
    - api.yourdomain.com
    - dashboard.yourdomain.com
    secretName: galaxy-tls
  rules:
  - host: api.yourdomain.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: authority-chain
            port:
              number: 1317
```

### 2. Persistent Storage

Configure storage class for production:

```bash
# Check available storage classes
kubectl get storageclass

# Update PVC in deployments to use specific storage class:
# storageClassName: fast-ssd  # or your production class
```

### 3. Resource Requests/Limits

Adjust based on your workload in deployment manifests:

```yaml
resources:
  requests:
    cpu: 500m
    memory: 512Mi
  limits:
    cpu: 1000m
    memory: 1Gi
```

### 4. Horizontal Pod Autoscaling

Create HPA for stateless services:

```bash
kubectl autoscale deployment edge-planet --min=3 --max=10 --cpu-percent=70
kubectl autoscale deployment predictive-service --min=2 --max=8 --cpu-percent=70
```

### 5. Secrets Management

For production, use external secrets:

```bash
# Using Sealed Secrets
kubectl apply -f https://github.com/bitnami-labs/sealed-secrets/releases/.../sealing-key.yaml

# Or AWS Secrets Manager
helm install external-secrets external-secrets/external-secrets

# Or HashiCorp Vault
helm install vault hashicorp/vault
```

## Backup & Restore

### Automated Daily Backups

Create a Kubernetes CronJob:

```bash
kubectl apply -f - <<EOF
apiVersion: batch/v1
kind: CronJob
metadata:
  name: galaxy-backup
  namespace: galaxy
spec:
  schedule: "2 * * * *"  # Every day at 2 AM
  jobTemplate:
    spec:
      template:
        spec:
          serviceAccountName: backup
          containers:
          - name: backup
            image: postgres:15-alpine
            command: ["/bin/sh", "-c"]
            args:
            - |
              /scripts/backup.sh
            volumeMounts:
            - name: backup-script
              mountPath: /scripts
            - name: backups
              mountPath: /backups
            env:
            - name: DATABASE_HOST
              value: postgres
            - name: DATABASE_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: postgres-secret
                  key: password
          volumes:
          - name: backup-script
            configMap:
              name: backup-script
              defaultMode: 0755
          - name: backups
            persistentVolumeClaim:
              claimName: backups-pvc
          restartPolicy: OnFailure
EOF
```

### Manual Restore

```bash
# Copy backup to pod
kubectl cp backups/galaxy_backup_20240327_120000.tar.gz galaxy/postgres-0:/tmp/

# Execute restore
kubectl exec -it galaxy/postgres-0 -- /scripts/restore.sh /tmp/galaxy_backup_*.tar.gz
```

## Monitoring & Observability

### Key Metrics to Monitor

- **Pod Status**: Restarts, OOMKilled, ImagePullBackOff
- **Resource Usage**: CPU, Memory, Disk I/O
- **Network**: Messages latency, Swarm node connectivity
- **Business Metrics**: Events submitted, verified, processed
- **Error Rates**: API errors, failed deliveries, processing failures

### Prometheus Scrape Targets

All services expose `/metrics` on port 8888:

```
- 'authority-chain.galaxy.svc.cluster.local:8888'
- 'edge-planet.galaxy.svc.cluster.local:8888'
- 'swarm-node.galaxy.svc.cluster.local:8888'
- 'fl-aggregator.galaxy.svc.cluster.local:8888'
- 'predictive-service.galaxy.svc.cluster.local:8888'
- 'webhook-service.galaxy.svc.cluster.local:8888'
- 'compliance-engine.galaxy.svc.cluster.local:8888'
- 'backend.galaxy.svc.cluster.local:8000'
```

### Creating Custom Dashboards

```bash
# Access Grafana UI
kubectl port-forward svc/grafana 3000:80 -n galaxy-monitoring

# Add Prometheus datasource:
# - URL: http://prometheus:9090
# - Access: Server (default)

# Import Galaxy main dashboard (import JSON from k8s/monitoring/grafana.yaml)
```

## Troubleshooting

### Pod Not Starting

```bash
# Check pod status and events
kubectl -n galaxy describe pod <pod-name>
kubectl -n galaxy logs <pod-name>

# Check resource availability
kubectl top nodes
kubectl describe nodes
```

### Service Connectivity Issues

```bash
# Test DNS
kubectl run -it --rm debug --image=busybox:1.28 --restart=Never -- nslookup service-name.galaxy.svc.cluster.local

# Check network policies
kubectl -n galaxy get networkpolicies
kubectl -n galaxy describe networkpolicies

# Test connectivity
kubectl exec -it <pod-name> -- sh
# Inside pod: curl http://target-service:port/health
```

### Persistent Volume Issues

```bash
# Check PV and PVC status
kubectl get pv
kubectl -n galaxy get pvc

# Check storage class
kubectl get storageclass

# Describe PVC for events
kubectl -n galaxy describe pvc <pvc-name>
```

### Certificate Issues

```bash
# Check certificate status
kubectl -n galaxy get certificate
kubectl -n galaxy describe certificate galaxy-tls

# Check certificate secret
kubectl -n galaxy get secret galaxy-tls -o yaml

# Renew certificate manually
kubectl -n galaxy delete secret galaxy-tls
kubectl -n galaxy delete certificate galaxy-tls
kubectl apply -f k8s/ingress.yaml
```

## Maintenance

### Rolling Updates

```bash
# Update deployment image
kubectl -n galaxy set image deployment/edge-planet \
  edge-planet=ghcr.io/repo/galaxy-edge-planet:v1.2.0

# Monitor rollout
kubectl -n galaxy rollout status deployment/edge-planet

# Rollback if needed
kubectl -n galaxy rollout undo deployment/edge-planet
```

### Scaling

```bash
# Manual scaling
kubectl -n galaxy scale deployment edge-planet --replicas=5

# View HPA status
kubectl -n galaxy get hpa
```

### Log Collection

```bash
# View logs from single pod
kubectl -n galaxy logs <pod-name>

# Stream logs
kubectl -n galaxy logs -f <pod-name>

# View logs from all pods in deployment
kubectl -n galaxy logs -l app=edge-planet --all-containers=true
```

## Security Best Practices

1. **Network Policies**: All deployments protected by zero-trust network policies
2. **RBAC**: Use least-privilege service accounts
3. **Secrets**: Store sensitive data in Kubernetes Secrets or external vaults
4. **Image Scanning**: All images scanned with Trivy for vulnerabilities
5. **Pod Security**: Run containers as non-root users
6. **TLS Encryption**: All ingress traffic encrypted with cert-manager
7. **Audit Logging**: Enable Kubernetes audit logging

## Performance Tuning

### Database Optimization

```sql
-- Enable query statistics
SHARED_PRELOAD_LIBRARIES = 'pg_stat_statements'

-- Connection pooling (pgBouncer)
kubectl apply -f k8s/pgbouncer-configmap.yaml
```

### Cache Optimization

```bash
# Monitor Redis memory
kubectl -n galaxy exec redis-0 -- redis-cli INFO memory

# Set eviction policy
kubectl -n galaxy exec redis-0 -- redis-cli CONFIG SET maxmemory-policy allkeys-lru
```

## Support & Documentation

- Kubernetes Documentation: https://kubernetes.io/docs/
- cert-manager: https://cert-manager.io/
- Prometheus: https://prometheus.io/
- Grafana: https://grafana.com/
- Trivy Scanner: https://github.com/aquasecurity/trivy

## Version Information

- Phase VI Release: 2024-03
- Kubernetes Target: 1.25+
- Images: Multi-architecture (amd64, arm64)
- Support: Community-driven, GitHub Issues

---

**Last Updated**: March 2024
**Maintained By**: Galaxy Team
