using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;

namespace aspnet_mvc.Controllers;

[Authorize(Roles = "Admin")]
public sealed class KnowledgeBaseController(IConfiguration configuration) : Controller
{
    public IActionResult Index()
    {
        ViewData["AgenticAppUrl"] =
            configuration["AgenticApp:PublicBaseUrl"] ?? "https://localhost:8000";
        return View();
    }
}
