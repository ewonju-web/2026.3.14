from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import Http404
from .models import SoilPost
from .forms import SoilPostForm


def soil_list(request):
    """현장 자재 나눔 목록."""
    material = (request.GET.get('material') or 'all').strip().lower()
    post_type = (request.GET.get('type') or 'all').strip().lower()

    material_tabs = [
        ('all', '전체'),
        ('soil', '흙·토사'),
        ('sand', '모래'),
        ('gravel', '자갈'),
        ('crushed', '잔석·쇄석'),
        ('block', '블록·벽돌'),
        ('concrete', '콘크리트 잔재'),
        ('other', '기타'),
    ]
    post_type_tabs = [
        ('all', '전체'),
        ('give', '드립니다'),
        ('take', '가져가실분'),
    ]

    valid_material = {k for k, _ in material_tabs}
    valid_post_type = {k for k, _ in post_type_tabs}
    if material not in valid_material:
        material = 'all'
    if post_type not in valid_post_type:
        post_type = 'all'

    posts = SoilPost.objects.filter(is_active=True).select_related('author').order_by('-created_at')
    if material != 'all':
        posts = posts.filter(material_type=material)
    if post_type != 'all':
        posts = posts.filter(post_type=post_type)

    return render(request, 'soil/soil_list.html', {
        'posts': posts,
        'material_tabs': material_tabs,
        'post_type_tabs': post_type_tabs,
        'selected_material': material,
        'selected_post_type': post_type,
    })


@login_required(login_url='/login/')
def soil_create(request):
    """등록 (로그인 필수)."""
    if request.method == 'POST':
        form = SoilPostForm(request.POST, request.FILES)
        if form.is_valid():
            post = form.save(commit=False)
            post.author = request.user
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
        form = SoilPostForm(request.POST, request.FILES, instance=post)
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
