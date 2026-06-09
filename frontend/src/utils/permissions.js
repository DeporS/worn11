export const canAccessModeration = (user) =>
	Boolean(
		user &&
			(user.is_staff ||
				user.is_superuser ||
				user.profile?.is_moderator),
	);
