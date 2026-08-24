---
id: "agent_devops_engineer"
name: "Lead DevOps & GitOps Engineer"
type: "agent_profile"
version: "2.0.0"
---

# Lead DevOps & GitOps Engineer Specification

## 1. Distroless Docker Build Standard
```dockerfile
FROM golang:1.22-alpine AS builder
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -ldflags="-w -s" -o /service-binary ./cmd/server

FROM gcr.io/distroless/static-debian12:nonroot
WORKDIR /
COPY --from=builder /service-binary /service-binary
USER nonroot:nonroot
EXPOSE 8080
ENTRYPOINT ["/service-binary"]
```

