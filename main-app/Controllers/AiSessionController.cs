using System.IdentityModel.Tokens.Jwt;
using System.Security.Claims;
using System.Text;
using aspnet_mvc.Models;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Identity;
using Microsoft.AspNetCore.Mvc;
using Microsoft.IdentityModel.Tokens;

namespace aspnet_mvc.Controllers;

[Authorize]
[Route("api/ai/session")]
public sealed class AiSessionController(
    UserManager<ApplicationUser> userManager,
    IConfiguration configuration) : Controller
{
    [HttpPost]
    [ValidateAntiForgeryToken]
    public async Task<IActionResult> CreateToken()
    {
        var userId = userManager.GetUserId(User);
        if (string.IsNullOrWhiteSpace(userId))
        {
            return Unauthorized();
        }

        var roles = await userManager.GetRolesAsync(await userManager.GetUserAsync(User)
            ?? throw new InvalidOperationException("The authenticated user could not be loaded."));
        var claims = new List<Claim>
        {
            new("sub", userId),
            new("name", User.Identity?.Name ?? string.Empty)
        };
        claims.AddRange(roles.Select(role => new Claim("role", role)));

        var key = new SymmetricSecurityKey(Encoding.UTF8.GetBytes(
            configuration["Ai:JwtSigningKey"]
            ?? throw new InvalidOperationException("Ai:JwtSigningKey is not configured.")));
        var token = new JwtSecurityToken(
            issuer: "service-desk-main-app",
            audience: "service-desk-agentic-app",
            claims: claims,
            notBefore: DateTime.UtcNow,
            expires: DateTime.UtcNow.AddMinutes(5),
            signingCredentials: new SigningCredentials(key, SecurityAlgorithms.HmacSha256));

        return Ok(new { accessToken = new JwtSecurityTokenHandler().WriteToken(token) });
    }
}
