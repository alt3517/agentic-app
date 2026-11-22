using aspnet_mvc.Data;
using aspnet_mvc.Models;
using Microsoft.AspNetCore.Authentication.JwtBearer;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;

namespace aspnet_mvc.Controllers;

[ApiController]
[Route("api/internal/tickets")]
[Authorize(AuthenticationSchemes = "AiJwt")]
public sealed class InternalTicketsController(ApplicationDbContext db) : ControllerBase
{
    [HttpPost("search")]
    public async Task<ActionResult<IReadOnlyList<TicketReadModel>>> Search(
        [FromBody] TicketSearchRequest request)
    {
        var tickets = db.Tickets.AsNoTracking();
        if (!User.IsInRole("Agent") && !User.IsInRole("Admin"))
        {
            var requesterId = User.FindFirst("sub")?.Value;
            if (string.IsNullOrWhiteSpace(requesterId))
            {
                return Forbid();
            }

            tickets = tickets.Where(ticket => ticket.CreatedById == requesterId);
        }

        if (!string.IsNullOrWhiteSpace(request.Query))
        {
            var term = request.Query.Trim();
            tickets = tickets.Where(ticket => ticket.Title.Contains(term) || ticket.Description.Contains(term));
        }

        var results = await tickets
            .OrderByDescending(ticket => ticket.UpdatedAtUtc)
            .Take(Math.Clamp(request.Limit, 1, 25))
            .Select(ticket => new TicketReadModel(
                ticket.Id,
                ticket.Title,
                ticket.Description,
                ticket.Category,
                ticket.Status.ToString(),
                ticket.Priority.ToString(),
                ticket.CreatedById,
                ticket.AssignedToId,
                ticket.UpdatedAtUtc))
            .ToListAsync();

        return Ok(results);
    }

    [HttpGet("{id:int}")]
    public async Task<ActionResult<TicketReadModel>> Get(int id)
    {
        var ticket = await db.Tickets.AsNoTracking().SingleOrDefaultAsync(item => item.Id == id);
        if (ticket is null)
        {
            return NotFound();
        }

        if (!User.IsInRole("Agent") && !User.IsInRole("Admin") &&
            ticket.CreatedById != User.FindFirst("sub")?.Value)
        {
            return NotFound();
        }

        return Ok(new TicketReadModel(
            ticket.Id,
            ticket.Title,
            ticket.Description,
            ticket.Category,
            ticket.Status.ToString(),
            ticket.Priority.ToString(),
            ticket.CreatedById,
            ticket.AssignedToId,
            ticket.UpdatedAtUtc));
    }
}

public sealed record TicketSearchRequest(string? Query, int Limit = 10);

public sealed record TicketReadModel(
    int Id,
    string Title,
    string Description,
    string Category,
    string Status,
    string Priority,
    string CreatedById,
    string? AssignedToId,
    DateTime UpdatedAtUtc);
