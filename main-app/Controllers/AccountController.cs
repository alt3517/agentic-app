using aspnet_mvc.Models;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Identity;
using Microsoft.AspNetCore.Mvc;

namespace aspnet_mvc.Controllers;

public sealed class AccountController(
    UserManager<ApplicationUser> userManager,
    SignInManager<ApplicationUser> signInManager) : Controller
{
    [AllowAnonymous]
    [HttpGet]
    public IActionResult Login(string? returnUrl = null)
    {
        ViewData["ReturnUrl"] = returnUrl;
        return View(new LoginInput());
    }

    [AllowAnonymous]
    [HttpPost]
    [ValidateAntiForgeryToken]
    public async Task<IActionResult> Login(LoginInput input, string? returnUrl = null)
    {
        ViewData["ReturnUrl"] = returnUrl;
        if (!ModelState.IsValid)
        {
            return View(input);
        }

        var result = await signInManager.PasswordSignInAsync(
            input.Email, input.Password, input.RememberMe, lockoutOnFailure: true);
        if (result.Succeeded)
        {
            return RedirectToLocal(returnUrl);
        }

        ModelState.AddModelError(string.Empty, result.IsLockedOut
            ? "Account temporarily locked. Try again later."
            : "Invalid email or password.");
        return View(input);
    }

    [AllowAnonymous]
    [HttpGet]
    public IActionResult Register() => View(new RegisterInput());

    [AllowAnonymous]
    [HttpPost]
    [ValidateAntiForgeryToken]
    public async Task<IActionResult> Register(RegisterInput input)
    {
        if (!ModelState.IsValid)
        {
            return View(input);
        }

        var user = new ApplicationUser
        {
            UserName = input.Email.Trim(),
            Email = input.Email.Trim(),
            DisplayName = input.DisplayName.Trim()
        };
        var result = await userManager.CreateAsync(user, input.Password);
        if (!result.Succeeded)
        {
            foreach (var error in result.Errors)
            {
                ModelState.AddModelError(string.Empty, error.Description);
            }

            return View(input);
        }

        var roleResult = await userManager.AddToRoleAsync(user, "Requester");
        if (!roleResult.Succeeded)
        {
            await userManager.DeleteAsync(user);
            throw new InvalidOperationException(
                $"Could not assign the requester role: {string.Join("; ", roleResult.Errors.Select(error => error.Description))}");
        }

        await signInManager.SignInAsync(user, isPersistent: false);
        return RedirectToAction("Index", "Tickets");
    }

    [Authorize]
    [HttpPost]
    [ValidateAntiForgeryToken]
    public async Task<IActionResult> Logout()
    {
        await signInManager.SignOutAsync();
        return RedirectToAction("Index", "Home");
    }

    [AllowAnonymous]
    public IActionResult AccessDenied() => View();

    private IActionResult RedirectToLocal(string? returnUrl) =>
        !string.IsNullOrEmpty(returnUrl) && Url.IsLocalUrl(returnUrl)
            ? LocalRedirect(returnUrl)
            : RedirectToAction("Index", "Tickets");
}
