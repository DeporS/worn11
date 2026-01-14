from decimal import Decimal
from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.exceptions import ObjectDoesNotExist

SHIRT_TECHNOLOGIES = [
    ('PLAYER_ISSUE', 'Player Issue'),
    ('REPLICA', 'Replica'),
    ('MATCH_WORN', 'Match Worn'),
]

SHIRT_TYPES = [
    ('Home', 'Home'),
    ('Away', 'Away'),
    ('Third', 'Third'),
    ('Fourth', 'Fourth'),
    ('Cup', 'Cup'),
    ('Training', 'Training'),
    ('GK', 'Goalkeeper'),
]

SIZE_CHOICES = [
    ('KIDS', 'Kids'),
    ('XS', 'Extra Small (XS)'),
    ('S', 'Small (S)'),
    ('M', 'Medium (M)'),
    ('L', 'Large (L)'),
    ('XL', 'Extra Large (XL)'),
    ('XXL', 'Double Extra Large (XXL)'),
    ('XXXL', 'Triple Extra Large (XXXL)'),
]

CONDITION_CHOICES = [
    ('BNWT', 'Brand New With Tags'),
    ('MINT', 'New Without Tags'),
    ('VERY_GOOD', 'Very Good Condition'),
    ('GOOD', 'Good Condition'),
    ('FAIR', 'Fair Condition'),
    ('POOR', 'Poor Condition'),
]

SIZE_MULTIPLIERS = {
    'KIDS': Decimal('0.25'),
    'XS': Decimal('0.4'),
    'S': Decimal('0.6'),
    'M': Decimal('0.9'),
    'L': Decimal('1.0'),
    'XL': Decimal('0.9'),
    'XXL': Decimal('0.75'),
    'XXXL': Decimal('0.6'),
}

CONDITION_MULTIPLIERS = {
    'BNWT': Decimal('2.0'),
    'MINT': Decimal('1.5'),
    'VERY_GOOD': Decimal('1.0'),
    'GOOD': Decimal('0.85'),
    'FAIR': Decimal('0.7'),
    'POOR': Decimal('0.5'),
}

TECHNOLOGIE_MULTIPLIERS = {
    'PLAYER_ISSUE': Decimal('1.5'),
    'REPLICA': Decimal('1.0'),
    'MATCH_WORN': Decimal('5.0'),
}

# User profile
class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    is_pro = models.BooleanField(default=False)  # Pro users have extra features
    is_moderator = models.BooleanField(default=False)  # Moderators can help manage content

    # pro_expiration_date = models.DateTimeField(null=True, blank=True)

    avatar = models.ImageField(upload_to='profile_avatars/', null=True, blank=True)
    bio = models.TextField(max_length=1000, blank=True)

    def __str__(self):
        return f"{self.user.username} Profile"

# Football Teams (ex. Barcelona, Real Madrid, etc.)
class Team(models.Model):
    name = models.CharField(max_length=100, unique=True)
    logo = models.ImageField(upload_to='team_logos/', null=True, blank=True)

    is_verified = models.BooleanField(default=False) # Admin can verify teams to avoid duplicates

    def __str__(self):
        return self.name
    
# Football Kits (ex. Arsenal Home 2021/2022)
class Kit(models.Model):
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='kits')
    season = models.CharField(max_length=20, help_text="e.g., 2021/2022") # e.g., "2021/2022"
    kit_type = models.CharField(max_length=50, help_text="e.g., Home, Away, Third") # e.g., "Home", "Away", "Third"

    # Simple pricing
    estimated_price = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="Estimated price in $ (Size L in Very Good condition)")
    
    # Only one image for context
    main_image = models.ImageField(upload_to='kit_images/', null=True, blank=True)

    def __str__(self):
        return f"{self.team.name} {self.kit_type} {self.season}"

# Users' Football Kits
class UserKit(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='collection')
    kit = models.ForeignKey(Kit, on_delete=models.CASCADE, related_name='owned_by')
    shirt_technology = models.CharField(max_length=20, choices=SHIRT_TECHNOLOGIES)
    condition = models.CharField(max_length=20, choices=CONDITION_CHOICES)
    size = models.CharField(max_length=10, choices=SIZE_CHOICES)
    player_name = models.CharField(max_length=100, null=True, blank=True)
    player_number = models.CharField(max_length=10, null=True, blank=True)
    for_sale = models.BooleanField(default=False)
    offer_link = models.URLField(max_length=500, null=True, blank=True)

    # How many users like this kit
    likes = models.ManyToManyField(User, related_name='liked_kits', blank=True)

    def total_likes(self):
        return self.likes.count()

    # When was added to the collection
    added_at = models.DateTimeField(auto_now_add=True)

    # Value fields
    manual_value = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text="Set your own value for the kit. If empty, the system will calculate it automatically."
    )

    final_value = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text="Final value of the kit, either manual or calculated."
    )

    def save(self, *args, **kwargs):
        # Calculate final value if manual_value is not set
        if self.manual_value:
            # If user set a manual value, use it
            self.final_value = self.manual_value
        else:
            # Calculate based on multipliers
            base_price = self.kit.estimated_price

            if base_price and base_price > 0:
                size_multiplier = SIZE_MULTIPLIERS.get(self.size, Decimal('1.0'))
                condition_multiplier = CONDITION_MULTIPLIERS.get(self.condition, Decimal('1.0'))
                technology_multiplier = TECHNOLOGIE_MULTIPLIERS.get(self.shirt_technology, Decimal('1.0'))

                calculated_value = base_price * size_multiplier * condition_multiplier * technology_multiplier
                self.final_value = calculated_value.quantize(Decimal('0.01'))  # Round to 2 decimal places
            else:
                self.final_value = Decimal('0.00')
        
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.user.username}'s {self.kit} ({self.size}, {self.condition})"
            
# Kit Images (multiple images per kit)
class UserKitImage(models.Model):
    user_kit = models.ForeignKey(UserKit, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='user_kits/')
    created_at = models.DateTimeField(auto_now_add=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']  
    
    def __str__(self):
        return f"Image for {self.user_kit}"



# SIGNALS

# Create or update user profile on User creation
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    try:
        instance.profile.save()
    except ObjectDoesNotExist:
        # Create profile if it does not exist
        Profile.objects.create(user=instance)
