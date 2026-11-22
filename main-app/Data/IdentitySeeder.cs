using aspnet_mvc.Models;
using Microsoft.AspNetCore.Identity;

namespace aspnet_mvc.Data;

public static class IdentitySeeder
{
    private static readonly string[] Roles = ["Requester", "Agent", "Admin"];

    public static async Task SeedAsync(IServiceProvider services, IConfiguration configuration)
    {
        using var scope = services.CreateScope();
        var roleManager = scope.ServiceProvider.GetRequiredService<RoleManager<IdentityRole>>();
        var userManager = scope.ServiceProvider.GetRequiredService<UserManager<ApplicationUser>>();
        var db = scope.ServiceProvider.GetRequiredService<ApplicationDbContext>();

        await db.Database.EnsureCreatedAsync();

        foreach (var role in Roles)
        {
            if (!await roleManager.RoleExistsAsync(role))
            {
                var result = await roleManager.CreateAsync(new IdentityRole(role));
                EnsureSucceeded(result);
            }
        }

        await SeedUserAsync(userManager, configuration, "SeedUsers:AdminEmail", "SeedUsers:AdminPassword", "Admin");
        await SeedUserAsync(userManager, configuration, "SeedUsers:AgentEmail", "SeedUsers:AgentPassword", "Agent");
    }

    private static async Task SeedUserAsync(
        UserManager<ApplicationUser> userManager,
        IConfiguration configuration,
        string emailKey,
        string passwordKey,
        string role)
    {
        var email = configuration[emailKey];
        var password = configuration[passwordKey];
        if (string.IsNullOrWhiteSpace(email) && string.IsNullOrWhiteSpace(password))
        {
            return;
        }

        if (string.IsNullOrWhiteSpace(email) || string.IsNullOrWhiteSpace(password))
        {
            throw new InvalidOperationException($"Both {emailKey} and {passwordKey} must be configured together.");
        }

        var user = await userManager.FindByEmailAsync(email);
        if (user is null)
        {
            user = new ApplicationUser
            {
                UserName = email,
                Email = email,
                EmailConfirmed = true,
                DisplayName = role
            };

            var createResult = await userManager.CreateAsync(user, password);
            EnsureSucceeded(createResult);
        }

        if (!await userManager.IsInRoleAsync(user, role))
        {
            var roleResult = await userManager.AddToRoleAsync(user, role);
            EnsureSucceeded(roleResult);
        }
    }

    private static void EnsureSucceeded(IdentityResult result)
    {
        if (!result.Succeeded)
        {
            throw new InvalidOperationException(
                $"Identity initialization failed: {string.Join("; ", result.Errors.Select(error => error.Description))}");
        }
    }
}
