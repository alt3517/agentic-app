# ASP.NET Core MVC ticket system

The .NET 10 MVC application owns user identity, roles, ticket data, and ticket authorization. It provides registration/sign-in, ticket workflows, an AI help page, an Admin-only knowledge-base page, and a short-lived JWT endpoint for the FastAPI service.

## Run locally

From this directory:

```powershell
dotnet run --launch-profile https
```

The app is available at <https://localhost:7161>. The user-seed settings and JWT signing key are environment variables; Docker Compose reads them from the repository-root `.env` file. See the [repository README](../README.md) for certificate setup and Compose instructions.

## Internal ticket API

`/api/internal/tickets` is read-only and requires a signed `AiJwt` token. Requesters see only their tickets; Agents and Admins may search all tickets. In Docker, the endpoint is reachable on port 8081 only on the Compose network. That internal HTTP listener is a local-demo-only exception; do not expose it or reuse it for shared deployments.

The browser obtains a short-lived AI token from `POST /api/ai/session`; the endpoint requires an authenticated MVC session and antiforgery validation.

## Integration tests

From the repository root:

```powershell
dotnet test main-app.Tests\main-app.Tests.csproj
```
