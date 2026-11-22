using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;

namespace aspnet_mvc.Controllers;

[Authorize]
public sealed class HelpController(IConfiguration configuration) : Controller
{
    public IActionResult Index(int? ticketId)
    {
        ViewData["AgenticAppUrl"] =
            configuration["AgenticApp:PublicBaseUrl"] ?? "https://localhost:8000";
        ViewData["TicketId"] = ticketId;
        return View();
    }
}
