from budget.models import HouseholdMember


class CurrentMemberMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            # On met en cache sur la requête pour éviter d'interroger la BDD plusieurs fois
            member = getattr(request, "_cached_member", None)
            if member is None:
                member = (
                    HouseholdMember.objects.filter(user=request.user, is_active=True)
                    .select_related("household")
                    .first()
                )
                request._cached_member = member
            request.member = member
            request.household = member.household if member else None
        else:
            request.member = None
            request.household = None

        return self.get_response(request)
