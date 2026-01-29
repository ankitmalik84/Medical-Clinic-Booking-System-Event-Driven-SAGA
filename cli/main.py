"""
Medical Clinic Booking System - CLI Client
Beautiful terminal interface with real-time status updates.
"""

import asyncio
import sys
from datetime import date, datetime
from typing import Optional, List

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, Confirm
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.live import Live
from rich.layout import Layout
from rich.text import Text
from rich import box

from api_client import BookingAPIClient

console = Console()


def print_header():
    """Print application header."""
    console.print()
    console.print(Panel.fit(
        "[bold blue]🏥 Medical Clinic Booking System[/bold blue]\n"
        "[dim]Event-Driven Transaction Demo[/dim]",
        border_style="blue",
        padding=(1, 4)
    ))
    console.print()


def print_services_table(services: list, gender: str):
    """Print services in a beautiful table."""
    table = Table(
        title=f"[bold]Available Services for {gender.capitalize()}[/bold]",
        box=box.ROUNDED,
        border_style="cyan"
    )
    
    table.add_column("#", style="dim", width=4)
    table.add_column("ID", style="cyan")
    table.add_column("Service", style="white")
    table.add_column("Price", justify="right", style="green")
    
    for i, service in enumerate(services, 1):
        table.add_row(
            str(i),
            service["id"],
            service["name"],
            f"₹{service['price']:,.0f}"
        )
    
    console.print(table)
    console.print()


def print_status_update(event: dict, is_final: bool = False):
    """Print a status update event."""
    msg = event.get("message", "")
    status = event.get("status", "")
    
    if "error" in event:
        console.print(f"  [red]✗[/red] {event['error']}")
    elif "final_result" in event:
        pass  # Handle separately
    elif is_final:
        console.print(f"  [green]✓[/green] {msg}")
    else:
        console.print(f"  [yellow]→[/yellow] {msg}")


def print_success_result(result: dict):
    """Print successful booking result."""
    console.print()
    
    panel_content = f"""[bold green]✅ BOOKING CONFIRMED[/bold green]

[bold]Reference:[/bold] {result.get('reference_id', 'N/A')}
[bold]Base Price:[/bold] ₹{result.get('base_price', 0):,.0f}"""
    
    if result.get('discount_applied'):
        discount = result.get('discount_percentage', 0)
        reason = result.get('discount_reason', 'Special Discount')
        panel_content += f"""
[bold]Discount:[/bold] [green]{discount}%[/green] ({reason})"""
    
    panel_content += f"""
[bold]Final Price:[/bold] [bold green]₹{result.get('final_price', 0):,.0f}[/bold green]

[dim]Services booked:[/dim]"""
    
    for service in result.get('services', []):
        panel_content += f"\n  • {service.get('name', 'Unknown')}"
    
    console.print(Panel(
        panel_content,
        border_style="green",
        padding=(1, 2)
    ))


def print_failure_result(result: dict):
    """Print failed booking result."""
    console.print()
    
    error_msg = result.get('error_message', 'Unknown error occurred')
    
    console.print(Panel(
        f"[bold red]❌ BOOKING FAILED[/bold red]\n\n"
        f"[bold]Reason:[/bold] {error_msg}\n\n"
        f"[dim]Request ID: {result.get('request_id', 'N/A')}[/dim]",
        border_style="red",
        padding=(1, 2)
    ))


async def run_booking_flow(client: BookingAPIClient):
    """Run the main booking flow."""
    print_header()
    
    # Step 1: Get user information
    console.print("[bold]Step 1: Enter Your Details[/bold]")
    console.print("-" * 40)
    
    name = Prompt.ask("[cyan]Enter your name[/cyan]")
    
    gender = Prompt.ask(
        "[cyan]Select gender[/cyan]",
        choices=["male", "female"],
        default="female"
    )
    
    while True:
        dob_str = Prompt.ask(
            "[cyan]Enter date of birth (YYYY-MM-DD)[/cyan]",
            default=datetime.now().strftime("%Y-%m-%d")  # Default to today for birthday demo
        )
        try:
            dob = date.fromisoformat(dob_str)
            break
        except ValueError:
            console.print("[red]Invalid date format. Use YYYY-MM-DD[/red]")
    
    console.print()
    
    # Step 2: Get and display services
    console.print("[bold]Step 2: Select Services[/bold]")
    console.print("-" * 40)
    
    with console.status("[bold green]Loading services..."):
        services_data = await client.get_services(gender)
    
    services = services_data.get("services", [])
    print_services_table(services, gender)
    
    # Select services
    while True:
        selection = Prompt.ask(
            "[cyan]Select services (comma-separated numbers, e.g., 1,2,3)[/cyan]"
        )
        try:
            indices = [int(x.strip()) - 1 for x in selection.split(",")]
            selected_ids = [services[i]["id"] for i in indices if 0 <= i < len(services)]
            if selected_ids:
                break
            console.print("[red]Please select at least one valid service[/red]")
        except (ValueError, IndexError):
            console.print("[red]Invalid selection. Enter comma-separated numbers[/red]")
    
    # Show selected services
    console.print()
    console.print("[bold]Selected Services:[/bold]")
    total = 0
    for sid in selected_ids:
        service = next((s for s in services if s["id"] == sid), None)
        if service:
            console.print(f"  • {service['name']} - ₹{service['price']:,.0f}")
            total += service['price']
    console.print(f"\n[bold]Estimated Total:[/bold] ₹{total:,.0f}")
    console.print()
    
    # Confirm
    if not Confirm.ask("[cyan]Proceed with booking?[/cyan]"):
        console.print("[yellow]Booking cancelled[/yellow]")
        return
    
    # Step 3: Process booking
    console.print()
    console.print("[bold]Step 3: Processing Booking[/bold]")
    console.print("-" * 40)
    console.print()
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True
    ) as progress:
        task = progress.add_task("[cyan]Submitting booking request...", total=None)
        
        try:
            # Submit booking
            response = await client.create_booking(name, gender, dob, selected_ids)
            request_id = response.get("request_id")
            
            progress.update(task, description=f"[cyan]Request ID: {request_id}")
            await asyncio.sleep(0.5)
            
        except Exception as e:
            console.print(f"[red]Error submitting booking: {e}[/red]")
            return
    
    # Get final result
    console.print(f"[dim]Request ID: {request_id}[/dim]")
    console.print()
    
    # Display events from the booking
    try:
        status_data = await client.get_booking_status(request_id)
        events = status_data.get("events", [])
        
        console.print("[bold]Transaction Events:[/bold]")
        for event in events:
            event_type = event.get("type", "")
            message = event.get("message", "")
            
            if "failed" in event_type.lower() or "exhausted" in event_type.lower():
                console.print(f"  [red]✗[/red] {message}")
            elif "completed" in event_type.lower() or "reserved" in event_type.lower():
                console.print(f"  [green]✓[/green] {message}")
            elif "compensation" in event_type.lower():
                console.print(f"  [yellow]↩[/yellow] {message}")
            else:
                console.print(f"  [blue]→[/blue] {message}")
        
        # Get and display final result
        result = await client.get_booking_result(request_id)
        
        if result.get("success"):
            print_success_result(result)
        else:
            print_failure_result(result)
            
    except Exception as e:
        console.print(f"[red]Error getting booking result: {e}[/red]")


async def run_test_scenario(client: BookingAPIClient, scenario: int):
    """Run a specific test scenario."""
    console.print()
    
    if scenario == 1:
        # Positive case: Birthday discount
        console.print(Panel(
            "[bold green]Test Scenario 1: Successful Birthday Discount[/bold green]\n\n"
            "• Female user with today as birthday\n"
            "• Multiple services selected\n"
            "• Expected: 12% birthday discount applied",
            border_style="green"
        ))
        
        # Reset quota first
        await client.reset_quota()
        await client.toggle_failure_simulation(False)
        
        today = date.today()
        name = "Priya Sharma"
        gender = "female"
        
        services_data = await client.get_services(gender)
        services = services_data.get("services", [])
        selected_ids = [services[0]["id"], services[1]["id"]]  # First two services
        
    elif scenario == 2:
        # Negative case: Quota exhausted
        console.print(Panel(
            "[bold red]Test Scenario 2: Quota Exhausted[/bold red]\n\n"
            "• Set quota to max limit\n"
            "• Female user with birthday (would qualify for discount)\n"
            "• Expected: Rejection due to quota exhaustion",
            border_style="red"
        ))
        
        # Set quota to max-1, then it will be exhausted
        await client.set_quota(100)  # Set to max
        await client.toggle_failure_simulation(False)
        
        today = date.today()
        name = "Anjali Mehta"
        gender = "female"
        
        services_data = await client.get_services(gender)
        services = services_data.get("services", [])
        selected_ids = [services[0]["id"]]
        
    elif scenario == 3:
        # Negative case: Booking failure with compensation
        console.print(Panel(
            "[bold red]Test Scenario 3: Booking Failure + Compensation[/bold red]\n\n"
            "• High-value order (>₹1000) to trigger R1 discount\n"
            "• Simulated booking service failure\n"
            "• Expected: Failure after quota reservation, compensation triggered",
            border_style="red"
        ))
        
        # Reset quota and enable failure
        await client.reset_quota()
        await client.toggle_failure_simulation(True)
        
        name = "Rahul Kumar"
        gender = "male"
        today = date(1990, 5, 15)  # Not birthday
        
        services_data = await client.get_services(gender)
        services = services_data.get("services", [])
        # Select high-value services (>1000)
        selected_ids = [s["id"] for s in services if s["price"] >= 500][:3]
        
    else:
        console.print("[red]Invalid scenario[/red]")
        return
    
    # Show what we're doing
    console.print()
    console.print(f"[bold]User:[/bold] {name}")
    console.print(f"[bold]Gender:[/bold] {gender}")
    console.print(f"[bold]DOB:[/bold] {today}")
    console.print(f"[bold]Services:[/bold] {selected_ids}")
    console.print()
    
    # Submit booking
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True
    ) as progress:
        task = progress.add_task("[cyan]Processing...", total=None)
        
        try:
            response = await client.create_booking(name, gender, today, selected_ids)
            request_id = response.get("request_id")
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            return
    
    # Display events
    console.print(f"[dim]Request ID: {request_id}[/dim]")
    console.print()
    
    status_data = await client.get_booking_status(request_id)
    events = status_data.get("events", [])
    
    console.print("[bold]Transaction Events:[/bold]")
    for event in events:
        event_type = event.get("type", "")
        message = event.get("message", "")
        
        if "failed" in event_type.lower() or "exhausted" in event_type.lower():
            console.print(f"  [red]✗[/red] {message}")
        elif "completed" in event_type.lower() or "reserved" in event_type.lower():
            console.print(f"  [green]✓[/green] {message}")
        elif "compensation" in event_type.lower():
            console.print(f"  [yellow]↩[/yellow] {message}")
        else:
            console.print(f"  [blue]→[/blue] {message}")
    
    # Get and display result
    result = await client.get_booking_result(request_id)
    
    if result.get("success"):
        print_success_result(result)
    else:
        print_failure_result(result)
    
    # Cleanup for scenario 3
    if scenario == 3:
        await client.toggle_failure_simulation(False)
        
        # Show compensation proof
        console.print()
        quota = await client.get_quota_status()
        console.print(f"[dim]Quota after compensation: {quota['current_count']}/{quota['max_quota']}[/dim]")


async def main_menu(client: BookingAPIClient):
    """Main menu loop."""
    while True:
        print_header()
        
        console.print("[bold]Main Menu[/bold]")
        console.print("-" * 40)
        console.print("1. [cyan]New Booking[/cyan] - Interactive booking flow")
        console.print("2. [green]Test Scenario 1[/green] - Successful birthday discount")
        console.print("3. [red]Test Scenario 2[/red] - Quota exhausted")
        console.print("4. [red]Test Scenario 3[/red] - Booking failure + compensation")
        console.print("5. [yellow]View Quota Status[/yellow]")
        console.print("6. [yellow]Reset Quota[/yellow]")
        console.print("0. [dim]Exit[/dim]")
        console.print()
        
        choice = Prompt.ask(
            "[cyan]Select option[/cyan]",
            choices=["0", "1", "2", "3", "4", "5", "6"],
            default="1"
        )
        
        if choice == "0":
            console.print("[dim]Goodbye![/dim]")
            break
        elif choice == "1":
            await run_booking_flow(client)
        elif choice == "2":
            await run_test_scenario(client, 1)
        elif choice == "3":
            await run_test_scenario(client, 2)
        elif choice == "4":
            await run_test_scenario(client, 3)
        elif choice == "5":
            quota = await client.get_quota_status()
            console.print()
            console.print(Panel(
                f"[bold]Quota Status[/bold]\n\n"
                f"Date: {quota['date']}\n"
                f"Used: {quota['current_count']}\n"
                f"Limit: {quota['max_quota']}\n"
                f"Remaining: {quota['remaining']}",
                border_style="yellow"
            ))
        elif choice == "6":
            await client.reset_quota()
            console.print("[green]Quota reset successfully[/green]")
        
        console.print()
        Prompt.ask("[dim]Press Enter to continue...[/dim]", default="")


async def main():
    """Main entry point."""
    # Get backend URL from environment or use default
    import os
    backend_url = os.getenv("BACKEND_URL", "http://localhost:8080")
    
    client = BookingAPIClient(backend_url)
    
    # Check health
    console.print("[dim]Connecting to backend...[/dim]")
    try:
        health = await client.health_check()
        if health.get("redis_connected"):
            console.print("[green]✓ Connected to backend[/green]")
        else:
            console.print("[yellow]⚠ Backend connected but Redis unavailable[/yellow]")
    except Exception as e:
        console.print(f"[red]✗ Failed to connect to backend: {e}[/red]")
        console.print(f"[dim]Make sure the backend is running at {backend_url}[/dim]")
        return
    
    await main_menu(client)


if __name__ == "__main__":
    asyncio.run(main())
