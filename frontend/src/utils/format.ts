import dayjs from 'dayjs'
import utc from 'dayjs/plugin/utc'

dayjs.extend(utc)

export function formatDate(date: string | Date, format = 'YYYY-MM-DD HH:mm:ss'): string {
  return dayjs.utc(date).local().format(format)
}

export function formatRelativeTime(date: string | Date): string {
  const now = dayjs()
  const target = dayjs.utc(date).local()
  const diffMinutes = now.diff(target, 'minute')

  if (diffMinutes < 1) return '刚刚'
  if (diffMinutes < 60) return `${diffMinutes}分钟前`

  const diffHours = now.diff(target, 'hour')
  if (diffHours < 24) return `${diffHours}小时前`

  const diffDays = now.diff(target, 'day')
  if (diffDays < 30) return `${diffDays}天前`

  const diffMonths = now.diff(target, 'month')
  if (diffMonths < 12) return `${diffMonths}个月前`

  return formatDate(date)
}

export function formatWordCount(count: number): string {
  if (count >= 10000) {
    return `${(count / 10000).toFixed(1)}万字`
  }
  if (count >= 1000) {
    return `${(count / 1000).toFixed(1)}千字`
  }
  return `${count}字`
}

export function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(2))} ${sizes[i]}`
}
