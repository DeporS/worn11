from .models import Kit, KitType, KitTypeAlias, TeamSeasonKitType, UserKit


def normalize_catalog_name(value):
    return ' '.join((value or '').strip().lower().split())


def kit_type_requires_team_season_suggestion(kit_type):
    if kit_type is None:
        return False

    return (
        kit_type.status == KitType.STATUS_PENDING
        or kit_type.default_visibility == KitType.VISIBILITY_NONE
    )


def resolve_kit_type_for_existing_kit(kit):
    if kit.kit_type_ref_id is not None:
        return kit.kit_type_ref

    cleaned_name = ' '.join((kit.kit_type or '').strip().split())
    if not cleaned_name:
        return None

    existing = KitType.objects.filter(name__iexact=cleaned_name).exclude(
        status=KitType.STATUS_MERGED,
    ).order_by('id').first()
    if existing is not None:
        return existing

    normalized_name = normalize_catalog_name(cleaned_name)
    if not normalized_name:
        return None

    alias = KitTypeAlias.objects.select_related('kit_type').filter(
        alias_normalized=normalized_name,
        kit_type__status=KitType.STATUS_APPROVED,
    ).first()
    return alias.kit_type if alias is not None else None


def ensure_team_season_suggestion(*, team, season, kit_type, created_by=None):
    if not getattr(team, 'is_verified', False):
        return None

    if not kit_type_requires_team_season_suggestion(kit_type):
        return None

    suggestion, _ = TeamSeasonKitType.objects.get_or_create(
        team=team,
        season=season,
        kit_type=kit_type,
        defaults={
            'status': TeamSeasonKitType.STATUS_PENDING,
            'source': TeamSeasonKitType.SOURCE_UPLOAD,
            'created_by': created_by,
        },
    )
    return suggestion


def create_team_season_suggestions_from_existing_kits(team):
    if not getattr(team, 'is_verified', False):
        raise ValueError('Team must be verified before creating team-season suggestions.')

    existing_rows = {
        (row.season, row.kit_type_id): row
        for row in TeamSeasonKitType.objects.select_for_update().filter(team=team).order_by('id')
    }

    first_user_by_kit_id = {}
    for kit_id, user_id in (
        UserKit.objects.filter(kit__team=team)
        .order_by('kit_id', 'added_at', 'id')
        .values_list('kit_id', 'user_id')
    ):
        first_user_by_kit_id.setdefault(kit_id, user_id)

    created = 0
    reused = 0
    seen_keys = set()

    kits = Kit.objects.select_related('kit_type_ref').filter(team=team).order_by('id')
    for kit in kits:
        resolved_kit_type = resolve_kit_type_for_existing_kit(kit)
        if not kit_type_requires_team_season_suggestion(resolved_kit_type):
            continue

        key = (kit.season, resolved_kit_type.id)
        if key in seen_keys:
            continue
        seen_keys.add(key)

        existing_row = existing_rows.get(key)
        if existing_row is not None:
            reused += 1
            continue

        suggestion = TeamSeasonKitType.objects.create(
            team=team,
            season=kit.season,
            kit_type=resolved_kit_type,
            status=TeamSeasonKitType.STATUS_PENDING,
            source=TeamSeasonKitType.SOURCE_UPLOAD,
            created_by_id=first_user_by_kit_id.get(kit.id),
        )
        existing_rows[key] = suggestion
        created += 1

    return {
        'created': created,
        'reused': reused,
    }
