using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;

namespace aspnet_mvc.Controllers;

[Authorize(Roles = "Admin")]
public sealed class OperationsController(IConfiguration configuration) : Controller
{
    public IActionResult Index()
    {
        ViewData["GrafanaDashboardUrl"] =
            configuration["Monitoring:GrafanaDashboardUrl"]
            ?? "http://localhost:3000/d/service-desk-operations/service-desk-operations?orgId=1&refresh=30s";
        return View();
    }
}
