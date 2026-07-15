# AWS Deployment Evidence (Phase 5b)

Full provision → validate → destroy cycle on AWS, executed per
`AWS_DEPLOYMENT_PLAN.md` (kept as an offline working document).

## Architecture

```
Docker build (local) ──push──> ECR (private registry, eu-central-1)
                                   │
                            App Runner service ── env vars: GROQ_API_KEY, GEMINI_API_KEY
                                   │                port 8080, 2 vCPU / 4 GB
                             Gradio app
                                   │ (first boot)
                        HF dataset repo (public) ──> downloads products.db + chroma (~2 GB)
```

## Evidence

| # | Screenshot | What it shows |
|---|---|---|
| 1 | `img/01-terraform-apply-output.png` | `terraform apply` creating the ECR repository; `ecr_repository_url` output |
| 2a/2b | `img/02-a-app-running-aws-url.png`, `img/02-b-app-running-aws-url.png` | The app reachable at the AWS App Runner URL |
| 3 | `img/03-app-running-hybrid-query.png` | Live hybrid-route query answered on the AWS URL: `supervisor(hybrid) → market_analyst → knowledge → critic(grounded) → supervisor(synthesize)`, sources cited, 9.5s latency |
| 4 | `img/04-app-runner-service-page.png` | AWS Console — App Runner service **Status: Running**, source image tag `v2` |
| 5 | `img/05-terminal.png` | `aws apprunner list-services` — `Status: RUNNING` |
| 6 | `img/06-destroy.png` | `terraform destroy` — `Destroy complete! Resources: 4 destroyed` |
| 7 | `img/07-check.png` | Residual check: App Runner list empty, ECR repository list empty, IAM role `NoSuchEntity` |

## Notable issue: WebSocket incompatibility (Streamlit → Gradio)

The first deployment used the Streamlit UI (identical to the one running on Streamlit
Community Cloud). The App Runner reverse proxy (Envoy) accepted the initial HTTPS
request (`curl` returned `200 OK` with the full Streamlit HTML) but rejected the
WebSocket upgrade Streamlit depends on for live updates (`wss://.../_stcore/stream`
failed in the browser console), leaving the page stuck on its loading skeleton.

Diagnosis path: DNS resolution verified → `curl -v` confirmed a healthy HTTP response →
browser DevTools Console isolated the failure to the WebSocket handshake → root cause
identified as an App Runner/Envoy limitation, not an application bug.

**Fix:** redeployed with the existing Gradio interface (`app.py`), which uses plain
HTTP request/response rather than a persistent WebSocket. This resolved the issue
completely — see evidence #3. Recorded as D9 in the decision log.

## Cost

Full cycle (ECR + two App Runner deployments, ~1.5 hours total runtime including the
Streamlit→Gradio redeploy) stayed within the planned **< $1** budget; App Runner was
paused during the local Docker rebuild to avoid idle billing. All resources destroyed
and verified absent (evidence #6, #7).

## Limitation

Terraform state is local (single-developer project); a production deployment would use
a remote backend (e.g., S3 + DynamoDB locking).
