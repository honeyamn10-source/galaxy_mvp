# ADR-0004: Kubernetes Production Readiness

- Status: Accepted
- Date: 2026-09-16
- Deciders: Bittu Sharma, CI

## Context
The Galaxy MVP targets production deployment on Kubernetes clusters (EKS, AKS,
GKE). All manifests must follow production-grade practices: resource limits,
health probes, network policies, secrets management, and RBAC.

## Decision
All k8s manifests under `k8s/` include:
- Resource requests/limits for every container
- Liveness and readiness probes
- Network policies restricting pod-to-pod communication
- Non-root security contexts
- SealedSecrets or Vault integration for secrets (template provided)
- PodDisruptionBudgets for HA components
- HorizontalPodAutoscaler for stateless services

## Consequences
- Manifests are audit-ready for SOC2/compliance reviews
- CI validates manifests with kubeconform and kubesec
- Deployments are repeatable across any CNCF-certified cluster
- Matches portfolio-wide production hardening standard
