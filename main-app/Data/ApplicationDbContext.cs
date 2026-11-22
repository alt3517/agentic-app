using aspnet_mvc.Models;
using Microsoft.AspNetCore.Identity.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore;

namespace aspnet_mvc.Data;

public sealed class ApplicationDbContext(DbContextOptions<ApplicationDbContext> options)
    : IdentityDbContext<ApplicationUser>(options)
{
    public DbSet<Ticket> Tickets => Set<Ticket>();

    protected override void OnModelCreating(ModelBuilder builder)
    {
        base.OnModelCreating(builder);

        builder.Entity<Ticket>()
            .HasOne(ticket => ticket.CreatedBy)
            .WithMany()
            .HasForeignKey(ticket => ticket.CreatedById)
            .OnDelete(DeleteBehavior.Restrict);

        builder.Entity<Ticket>()
            .HasOne(ticket => ticket.AssignedTo)
            .WithMany()
            .HasForeignKey(ticket => ticket.AssignedToId)
            .OnDelete(DeleteBehavior.SetNull);

        builder.Entity<Ticket>()
            .HasIndex(ticket => new { ticket.CreatedById, ticket.CreatedAtUtc });

        builder.Entity<Ticket>()
            .HasIndex(ticket => new { ticket.Status, ticket.Priority });
    }
}
