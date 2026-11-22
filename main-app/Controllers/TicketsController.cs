using aspnet_mvc.Data;
using aspnet_mvc.Models;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Identity;
using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.Mvc.Rendering;
using Microsoft.EntityFrameworkCore;

namespace aspnet_mvc.Controllers;

[Authorize]
public sealed class TicketsController(
    ApplicationDbContext db,
    UserManager<ApplicationUser> userManager) : Controller
{
    public async Task<IActionResult> Index(string? q, TicketStatus? status)
    {
        var tickets = VisibleTickets();
        if (!string.IsNullOrWhiteSpace(q))
        {
            var term = q.Trim();
            tickets = tickets.Where(ticket =>
                ticket.Title.Contains(term) || ticket.Description.Contains(term));
        }

        if (status.HasValue)
        {
            tickets = tickets.Where(ticket => ticket.Status == status.Value);
        }

        ViewData["Query"] = q;
        ViewData["Status"] = status;
        return View(await tickets
            .OrderByDescending(ticket => ticket.UpdatedAtUtc)
            .ToListAsync());
    }

    public async Task<IActionResult> Details(int id)
    {
        var ticket = await VisibleTickets()
            .Include(item => item.CreatedBy)
            .Include(item => item.AssignedTo)
            .SingleOrDefaultAsync(item => item.Id == id);
        return ticket is null ? NotFound() : View(ticket);
    }

    public IActionResult Create() => View(new TicketInput());

    [HttpPost]
    [ValidateAntiForgeryToken]
    public async Task<IActionResult> Create(TicketInput input)
    {
        if (!ModelState.IsValid)
        {
            return View(input);
        }

        var ticket = new Ticket
        {
            Title = input.Title.Trim(),
            Description = input.Description.Trim(),
            Category = input.Category.Trim(),
            CreatedById = userManager.GetUserId(User)!,
            CreatedAtUtc = DateTime.UtcNow,
            UpdatedAtUtc = DateTime.UtcNow
        };
        db.Tickets.Add(ticket);
        await db.SaveChangesAsync();
        return RedirectToAction(nameof(Details), new { id = ticket.Id });
    }

    public async Task<IActionResult> Edit(int id)
    {
        var ticket = await FindVisibleTicket(id);
        if (ticket is null)
        {
            return NotFound();
        }

        if (!CanManage() && ticket.Status is TicketStatus.Resolved or TicketStatus.Closed)
        {
            return Forbid();
        }

        await PopulateAssignees();
        return View(new TicketInput
        {
            Title = ticket.Title,
            Description = ticket.Description,
            Category = ticket.Category,
            Status = ticket.Status,
            Priority = ticket.Priority,
            AssignedToId = ticket.AssignedToId
        });
    }

    [HttpPost]
    [ValidateAntiForgeryToken]
    public async Task<IActionResult> Edit(int id, TicketInput input)
    {
        var ticket = await FindVisibleTicket(id);
        if (ticket is null)
        {
            return NotFound();
        }

        if (!CanManage() && ticket.Status is TicketStatus.Resolved or TicketStatus.Closed)
        {
            return Forbid();
        }

        if (!ModelState.IsValid)
        {
            await PopulateAssignees();
            return View(input);
        }

        ticket.Title = input.Title.Trim();
        ticket.Description = input.Description.Trim();
        ticket.Category = input.Category.Trim();
        if (CanManage())
        {
            if (Enum.IsDefined(input.Status) && Enum.IsDefined(input.Priority))
            {
                ticket.Status = input.Status;
                ticket.Priority = input.Priority;
            }

            ticket.AssignedToId = await IsStaffUser(input.AssignedToId) ? input.AssignedToId : null;
        }

        ticket.UpdatedAtUtc = DateTime.UtcNow;
        await db.SaveChangesAsync();
        return RedirectToAction(nameof(Details), new { id });
    }

    [Authorize(Roles = "Agent,Admin")]
    public async Task<IActionResult> Delete(int id)
    {
        var ticket = await VisibleTickets()
            .Include(item => item.CreatedBy)
            .SingleOrDefaultAsync(item => item.Id == id);
        return ticket is null ? NotFound() : View(ticket);
    }

    [Authorize(Roles = "Agent,Admin")]
    [HttpPost, ActionName("Delete")]
    [ValidateAntiForgeryToken]
    public async Task<IActionResult> DeleteConfirmed(int id)
    {
        var ticket = await db.Tickets.FindAsync(id);
        if (ticket is null)
        {
            return NotFound();
        }

        db.Tickets.Remove(ticket);
        await db.SaveChangesAsync();
        return RedirectToAction(nameof(Index));
    }

    private IQueryable<Ticket> VisibleTickets()
    {
        var query = db.Tickets.AsNoTracking();
        if (User.IsInRole("Agent") || User.IsInRole("Admin"))
        {
            return query.Include(ticket => ticket.CreatedBy).Include(ticket => ticket.AssignedTo);
        }

        var userId = userManager.GetUserId(User);
        return query.Where(ticket => ticket.CreatedById == userId)
            .Include(ticket => ticket.CreatedBy)
            .Include(ticket => ticket.AssignedTo);
    }

    private Task<Ticket?> FindVisibleTicket(int id) =>
        VisibleTickets().SingleOrDefaultAsync(ticket => ticket.Id == id);

    private bool CanManage() =>
        User.IsInRole("Agent") || User.IsInRole("Admin");

    private async Task<bool> IsStaffUser(string? userId)
    {
        if (string.IsNullOrWhiteSpace(userId))
        {
            return false;
        }

        var user = await userManager.FindByIdAsync(userId);
        return user is not null &&
               (await userManager.IsInRoleAsync(user, "Agent") || await userManager.IsInRoleAsync(user, "Admin"));
    }

    private async Task PopulateAssignees()
    {
        var staff = await userManager.GetUsersInRoleAsync("Agent");
        var admins = await userManager.GetUsersInRoleAsync("Admin");
        ViewData["Assignees"] = new SelectList(
            staff.Concat(admins).DistinctBy(user => user.Id).OrderBy(user => user.DisplayName),
            "Id",
            "DisplayName");
    }
}
