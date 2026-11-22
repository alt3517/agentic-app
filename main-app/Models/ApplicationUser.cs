using Microsoft.AspNetCore.Identity;

namespace aspnet_mvc.Models;

public sealed class ApplicationUser : IdentityUser
{
    public string DisplayName { get; set; } = string.Empty;
}
