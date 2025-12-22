from django.shortcuts import render
from .models import UserKit

def my_collection(request):
    # Download all UserKit objects for the logged-in user
    my_kits = UserKit.objects.select_related('kit', 'kit__team').all()
    
    # Calculate the total value of the collection
    total_value = sum(item.final_value for item in my_kits)

    return render(request, 'kits/index.html', {
        'my_kits': my_kits,
        'total_value': total_value
    })