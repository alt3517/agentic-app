using System.ComponentModel.DataAnnotations;

namespace aspnet_mvc.Models;

public enum TicketStatus
{
    New,
    Open,
    InProgress,
    WaitingForCustomer,
    Resolved,
    Closed
}

public enum TicketPriority
{
    Low,
    Normal,
    High,
    Urgent
}

public sealed class Ticket
{
    public int Id { get; set; }

    [Required, StringLength(160)]
    public string Title { get; set; } = string.Empty;

    [Required, StringLength(10000, MinimumLength = 10)]
    public string Description { get; set; } = string.Empty;

    [Required, StringLength(80)]
    public string Category { get; set; } = "General";

    public TicketStatus Status { get; set; } = TicketStatus.New;
    public TicketPriority Priority { get; set; } = TicketPriority.Normal;

    [Required]
    public string CreatedById { get; set; } = string.Empty;
    public ApplicationUser CreatedBy { get; set; } = null!;

    public string? AssignedToId { get; set; }
    public ApplicationUser? AssignedTo { get; set; }

    public DateTime CreatedAtUtc { get; set; } = DateTime.UtcNow;
    public DateTime UpdatedAtUtc { get; set; } = DateTime.UtcNow;
}
