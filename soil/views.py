from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import Http404
from .models import SoilPost
from .forms import SoilPostForm


def soil_list(request):
    """흙 받으실분 목록 (1차: need만)."""
    posts = SoilPost.objects.filter(post_type='need', is_active=True).select_related('author').order_by('-created_at')
    return render(request, 'soil/soil_list.html', {'posts': posts})


@login_required(login_url='/login/')
def soil_create(request):
    """등록 (로그인 필수)."""
    if request.method == 'POST':
        form = SoilPostForm(request.POST)
        if form.is_valid():
            post = form.save(commit=False)
            post.author = request.user
            post.post_type = 'need'
            post.save()
            return redirect('soil_detail', pk=post.pk)
    else:
        form = SoilPostForm()
    return render(request, 'soil/soil_form.html', {'form': form, 'is_edit': False})


def soil_detail(request, pk):
    """상세."""
    post = get_object_or_404(SoilPost, pk=pk, is_active=True)
    can_edit = request.user.is_authenticated and post.author_id == request.user.id
    return render(request, 'soil/soil_detail.html', {'post': post, 'can_edit': can_edit})


@login_required(login_url='/login/')
def soil_edit(request, pk):
    """수정 (작성자만)."""
    post = get_object_or_404(SoilPost, pk=pk)
    if post.author_id != request.user.id:
        raise Http404()
    if request.method == 'POST':
        form = SoilPostForm(request.POST, instance=post)
        if form.is_valid():
            form.save()
            return redirect('soil_detail', pk=pk)
    else:
        form = SoilPostForm(instance=post)
    return render(request, 'soil/soil_form.html', {'form': form, 'post': post, 'is_edit': True})


@login_required(login_url='/login/')
def soil_delete(request, pk):
    """삭제 (작성자만)."""
    post = get_object_or_404(SoilPost, pk=pk)
    if post.author_id != request.user.id:
        raise Http404()
    if request.method == 'POST':
        post.delete()
        return redirect('soil_list')
    return render(request, 'soil/soil_confirm_delete.html', {'post': post})
