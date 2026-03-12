from django.conf import settings
from django.db import models


class ChatRoom(models.Model):
    """매물 또는 흙 게시글 기준 1:1 채팅방. equipment 또는 soil_post 중 하나만 설정."""
    equipment = models.ForeignKey(
        'equipment.Equipment',
        on_delete=models.CASCADE,
        related_name='chat_rooms',
        verbose_name='매물',
        null=True,
        blank=True,
    )
    soil_post = models.ForeignKey(
        'soil.SoilPost',
        on_delete=models.CASCADE,
        related_name='chat_rooms',
        verbose_name='흙 게시글',
        null=True,
        blank=True,
    )
    job_post = models.ForeignKey(
        'equipment.JobPost',
        on_delete=models.CASCADE,
        related_name='chat_rooms',
        verbose_name='구인구직 글',
        null=True,
        blank=True,
    )
    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='chatrooms_as_buyer',
        verbose_name='구매자(문의자)',
    )
    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='chatrooms_as_seller',
        verbose_name='판매자',
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='생성일시')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='수정일시')
    last_message_at = models.DateTimeField(null=True, blank=True, verbose_name='마지막 메시지 시각')

    class Meta:
        verbose_name = '채팅방'
        verbose_name_plural = '채팅방'
        constraints = [
            models.UniqueConstraint(
                fields=['equipment', 'buyer', 'seller'],
                name='unique_equipment_buyer_seller',
                condition=models.Q(equipment__isnull=False),
            ),
            models.UniqueConstraint(
                fields=['soil_post', 'buyer', 'seller'],
                name='unique_soil_post_buyer_seller',
                condition=models.Q(soil_post__isnull=False),
            ),
            models.UniqueConstraint(
                fields=['job_post', 'buyer', 'seller'],
                name='unique_job_post_buyer_seller',
                condition=models.Q(job_post__isnull=False),
            ),
        ]
        ordering = ['-last_message_at', '-updated_at']

    def __str__(self):
        if self.equipment_id:
            return f'매물 {self.equipment_id} / {self.buyer.username} ↔ {self.seller.username}'
        if self.soil_post_id:
            return f'흙 {self.soil_post_id} / {self.buyer.username} ↔ {self.seller.username}'
        if self.job_post_id:
            return f'구인구직 {self.job_post_id} / {self.buyer.username} ↔ {self.seller.username}'
        return f'{self.buyer.username} ↔ {self.seller.username}'


class ChatMessage(models.Model):
    """채팅 메시지."""
    room = models.ForeignKey(
        ChatRoom,
        on_delete=models.CASCADE,
        related_name='messages',
        verbose_name='채팅방',
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='chat_messages_sent',
        verbose_name='발신자',
    )
    message = models.TextField(verbose_name='메시지')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='발송일시')
    is_read = models.BooleanField(default=False, verbose_name='읽음 여부')

    class Meta:
        verbose_name = '채팅 메시지'
        verbose_name_plural = '채팅 메시지'
        ordering = ['created_at']

    def __str__(self):
        return f'{self.room_id} / {self.sender.username} @ {self.created_at}'
