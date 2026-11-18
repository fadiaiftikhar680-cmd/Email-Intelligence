"""
Company and People Intelligence Views.
Fulfills Part 10 (S-12 and S-13).
"""
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from apps.email_finder.models import Company, Person, DiscoveredEmail


@login_required
def company_intelligence_view(request, company_id):
    """S-12: Company Intelligence Profile with source-tracked facts."""
    company = get_object_or_404(Company, id=company_id, owner=request.user)
    employees = company.employees.all()
    emails = company.emails.all()
    return render(request, "intelligence/company.html", {
        "company": company,
        "employees": employees,
        "emails": emails,
    })


@login_required
def person_intelligence_view(request, person_id):
    """S-13: People Intelligence Profile with source-tracked facts."""
    person = get_object_or_404(Person, id=person_id, owner=request.user)
    emails = person.emails.all()
    return render(request, "intelligence/person.html", {
        "person": person,
        "emails": emails,
    })


@login_required
def intelligence_directory_view(request):
    """Directory of discovered companies and people."""
    companies = Company.objects.filter(owner=request.user)
    people = Person.objects.filter(owner=request.user)
    return render(request, "intelligence/directory.html", {
        "companies": companies,
        "people": people,
    })

