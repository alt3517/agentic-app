FROM mcr.microsoft.com/dotnet/sdk:10.0 AS build
WORKDIR /src

COPY main-app/aspnet-mvc.csproj main-app/
RUN dotnet restore main-app/aspnet-mvc.csproj

COPY main-app/ main-app/
WORKDIR /src/main-app
RUN dotnet publish aspnet-mvc.csproj \
    --configuration Release \
    --no-restore \
    --output /app/publish \
    /p:UseAppHost=false

FROM mcr.microsoft.com/dotnet/aspnet:10.0 AS runtime
WORKDIR /app
COPY --from=build /app/publish .
USER root
RUN mkdir -p /app/data && chown 10001:10001 /app/data
USER 10001:10001

ENV ASPNETCORE_URLS=https://+:8080
EXPOSE 8080

ENTRYPOINT ["dotnet", "aspnet-mvc.dll"]
