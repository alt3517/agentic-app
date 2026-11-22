using System.Net;
using System.Net.Http.Headers;
using System.Net.Http.Json;
using System.Text.RegularExpressions;
using aspnet_mvc.Models;
using Microsoft.AspNetCore.Identity;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.Data.Sqlite;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;

namespace main_app.Tests;

public sealed class MvcAppFactory : WebApplicationFactory<Program>
{
    private const string TestSigningKey = "test-signing-key-that-is-at-least-thirty-two-bytes";
    private readonly string _databasePath = Path.Combine(
        Path.GetTempPath(),
        $"service-desk-tests-{Guid.NewGuid():N}.db");
    private readonly string? _previousSigningKey = Environment.GetEnvironmentVariable("Ai__JwtSigningKey");
    private readonly string? _previousConnectionString = Environment.GetEnvironmentVariable("ConnectionStrings__DefaultConnection");

    public MvcAppFactory()
    {
        Environment.SetEnvironmentVariable("Ai__JwtSigningKey", TestSigningKey);
        Environment.SetEnvironmentVariable(
            "ConnectionStrings__DefaultConnection",
            $"Data Source={_databasePath}");
    }

    protected override void ConfigureWebHost(IWebHostBuilder builder)
    {
        builder.UseEnvironment("Testing");
        builder.ConfigureAppConfiguration((_, configuration) =>
        {
            configuration.AddInMemoryCollection(new Dictionary<string, string?>
            {
                ["ConnectionStrings:DefaultConnection"] = $"Data Source={_databasePath}",
                ["Ai:JwtSigningKey"] = "test-signing-key-that-is-at-least-thirty-two-bytes",
                ["Monitoring:GrafanaDashboardUrl"] = "https://grafana.example.test/d/service-desk-operations/service-desk-operations"
            });
        });
    }

    protected override void Dispose(bool disposing)
    {
        base.Dispose(disposing);
        if (disposing)
        {
            Environment.SetEnvironmentVariable("Ai__JwtSigningKey", _previousSigningKey);
            Environment.SetEnvironmentVariable("ConnectionStrings__DefaultConnection", _previousConnectionString);
            if (File.Exists(_databasePath))
            {
                SqliteConnection.ClearAllPools();
                File.Delete(_databasePath);
            }
        }
    }
}

public sealed class MvcIntegrationTests(MvcAppFactory factory) : IClassFixture<MvcAppFactory>
{
    [Fact]
    public async Task Home_page_is_available()
    {
        using var client = factory.CreateClient();
        using var response = await client.GetAsync("/");
        var content = await response.Content.ReadAsStringAsync();

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        Assert.Contains("Service Desk", content);
    }

    [Fact]
    public async Task Requester_can_register_and_create_a_ticket()
    {
        using var client = factory.CreateClient(new WebApplicationFactoryClientOptions
        {
            BaseAddress = new Uri("https://localhost"),
            AllowAutoRedirect = false,
            HandleCookies = true
        });

        var registrationPage = await client.GetStringAsync("/Account/Register");
        var registrationToken = GetAntiforgeryToken(registrationPage);
        var requesterEmail = $"requester-{Guid.NewGuid():N}@example.test";
        const string requesterPassword = "GoodPassword1!";
        using var registration = await client.PostAsync("/Account/Register", Form(
            ("__RequestVerificationToken", registrationToken),
            ("DisplayName", "Demo Requester"),
            ("Email", requesterEmail),
            ("Password", requesterPassword),
            ("ConfirmPassword", requesterPassword)));
        Assert.Equal(HttpStatusCode.Redirect, registration.StatusCode);

        var createPage = await client.GetStringAsync("/Tickets/Create");
        var createToken = GetAntiforgeryToken(createPage);
        using var createTicket = await client.PostAsync("/Tickets/Create", Form(
            ("__RequestVerificationToken", createToken),
            ("Title", "VPN access issue"),
            ("Description", "The company VPN rejects the new laptop."),
            ("Category", "Access")));
        Assert.Equal(HttpStatusCode.Redirect, createTicket.StatusCode);

        var ticketList = await client.GetStringAsync("/Tickets");
        Assert.Contains("VPN access issue", ticketList);

        using var helpPage = await client.GetAsync("/Help");
        Assert.Equal(HttpStatusCode.OK, helpPage.StatusCode);

        var helpHtml = await helpPage.Content.ReadAsStringAsync();
        Assert.DoesNotContain("Agent Copilot", helpHtml);
        using var operationsDenied = await client.GetAsync("/Operations");
        Assert.Equal(HttpStatusCode.Redirect, operationsDenied.StatusCode);
        using var tokenRequest = new HttpRequestMessage(HttpMethod.Post, "/api/ai/session");
        tokenRequest.Headers.Add("RequestVerificationToken", GetAntiforgeryToken(helpHtml));
        using var tokenResponse = await client.SendAsync(tokenRequest);
        var tokenPayload = await tokenResponse.Content.ReadAsStringAsync();
        Assert.Equal(HttpStatusCode.OK, tokenResponse.StatusCode);
        Assert.Contains("accessToken", tokenPayload);
        using var tokenDocument = System.Text.Json.JsonDocument.Parse(tokenPayload);
        var accessToken = tokenDocument.RootElement.GetProperty("accessToken").GetString();
        using var searchRequest = new HttpRequestMessage(HttpMethod.Post, "/api/internal/tickets/search")
        {
            Content = JsonContent.Create(new { query = "VPN", limit = 10 })
        };
        searchRequest.Headers.Authorization = new AuthenticationHeaderValue("Bearer", accessToken);
        using var searchResponse = await client.SendAsync(searchRequest);
        var searchPayload = await searchResponse.Content.ReadAsStringAsync();

        Assert.Equal(HttpStatusCode.OK, searchResponse.StatusCode);
        Assert.Contains("VPN access issue", searchPayload);
        Assert.DoesNotContain("VPN", searchRequest.RequestUri!.Query);

        var ticketLink = Regex.Match(ticketList, "href=\"/Tickets/Details/(\\d+)\"", RegexOptions.CultureInvariant);
        Assert.True(ticketLink.Success, "The ticket list did not contain a link to the created ticket.");
        var ticketId = ticketLink.Groups[1].Value;

        using (var scope = factory.Services.CreateScope())
        {
            var userManager = scope.ServiceProvider.GetRequiredService<UserManager<ApplicationUser>>();
            var registeredUser = await userManager.FindByEmailAsync(requesterEmail);
            Assert.NotNull(registeredUser);
            var agentRoleResult = await userManager.AddToRoleAsync(registeredUser, "Agent");
            var adminRoleResult = await userManager.AddToRoleAsync(registeredUser, "Admin");
            Assert.True(agentRoleResult.Succeeded);
            Assert.True(adminRoleResult.Succeeded);
        }

        using var agentClient = factory.CreateClient(new WebApplicationFactoryClientOptions
        {
            BaseAddress = new Uri("https://localhost"),
            AllowAutoRedirect = false,
            HandleCookies = true
        });
        var loginPage = await agentClient.GetStringAsync("/Account/Login");
        using var loginResponse = await agentClient.PostAsync("/Account/Login", Form(
            ("__RequestVerificationToken", GetAntiforgeryToken(loginPage)),
            ("Email", requesterEmail),
            ("Password", requesterPassword)));
        Assert.Equal(HttpStatusCode.Redirect, loginResponse.StatusCode);

        var agentHelp = await agentClient.GetStringAsync($"/Help?ticketId={ticketId}");
        Assert.Contains("Agent Copilot", agentHelp);
        Assert.Contains($"value=\"{ticketId}\"", agentHelp);
        Assert.Contains("This is the only input Copilot needs", agentHelp);
        Assert.Contains("It will not change the ticket or send the reply", agentHelp);

        var operationsPage = await agentClient.GetStringAsync("/Operations");
        Assert.Contains("Operations monitoring", operationsPage);
        Assert.Contains("Open Grafana dashboard", operationsPage);
        Assert.Contains("https://grafana.example.test/d/service-desk-operations/service-desk-operations", operationsPage);
        Assert.Contains("Check Prometheus targets", operationsPage);
        Assert.Contains("HTTP 5xx error rate", operationsPage);
    }

    [Fact]
    public async Task Read_only_ticket_api_requires_a_signed_user_token()
    {
        using var client = factory.CreateClient(new WebApplicationFactoryClientOptions
        {
            BaseAddress = new Uri("https://localhost")
        });

        using var response = await client.PostAsJsonAsync(
            "/api/internal/tickets/search",
            new { query = "sensitive-search-term", limit = 10 });

        Assert.Equal(HttpStatusCode.Unauthorized, response.StatusCode);
    }

    private static FormUrlEncodedContent Form(params (string Key, string Value)[] values) =>
        new(values.Select(value => new KeyValuePair<string, string>(value.Key, value.Value)));

    private static string GetAntiforgeryToken(string html)
    {
        var match = Regex.Match(
            html,
            "name=\"__RequestVerificationToken\"[^>]*value=\"([^\"]+)\"",
            RegexOptions.CultureInvariant);
        Assert.True(match.Success, "The page did not contain an antiforgery token.");
        return WebUtility.HtmlDecode(match.Groups[1].Value);
    }
}
