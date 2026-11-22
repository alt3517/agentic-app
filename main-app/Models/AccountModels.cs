using System.ComponentModel.DataAnnotations;

namespace aspnet_mvc.Models;

public sealed class RegisterInput
{
    [Required, StringLength(80, MinimumLength = 2)]
    public string DisplayName { get; set; } = string.Empty;

    [Required, EmailAddress, StringLength(256)]
    public string Email { get; set; } = string.Empty;

    [Required, DataType(DataType.Password), StringLength(100, MinimumLength = 12)]
    public string Password { get; set; } = string.Empty;

    [Required, DataType(DataType.Password), Compare(nameof(Password))]
    public string ConfirmPassword { get; set; } = string.Empty;
}

public sealed class LoginInput
{
    [Required, EmailAddress]
    public string Email { get; set; } = string.Empty;

    [Required, DataType(DataType.Password)]
    public string Password { get; set; } = string.Empty;

    public bool RememberMe { get; set; }
}

public sealed class TicketInput
{
    [Required, StringLength(160)]
    public string Title { get; set; } = string.Empty;

    [Required, StringLength(10000, MinimumLength = 10)]
    public string Description { get; set; } = string.Empty;

    [Required, StringLength(80)]
    public string Category { get; set; } = "General";

    public TicketStatus Status { get; set; } = TicketStatus.New;
    public TicketPriority Priority { get; set; } = TicketPriority.Normal;
    public string? AssignedToId { get; set; }
}
