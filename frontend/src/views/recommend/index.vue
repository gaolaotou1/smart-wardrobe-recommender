<template>
  <div class="recommend-container">


    <!-- 主要内容区域 -->
    <div class="main-content">
      <!-- 左侧衣物选择区 -->
      <div class="clothes-selection">
        <div class="section-title">
          <div class="operation-bar">
            <div class="left">
              <!-- <el-button type="primary" @click="handleAddClothes" class="add-button">
                <el-icon><Plus /></el-icon>添加衣物
              </el-button> -->
              <el-button @click="toggleSelectAll" class="select-all-button">
                <el-icon><Select /></el-icon>{{ isAllSelected ? '取消全选' : '全选' }}
              </el-button>
            </div>
            <div class="right">
              <el-input
                v-model="searchKeyword"
                placeholder="搜索衣物"
                class="search-input"
                clearable
                @clear="handleSearch"
                @input="handleSearch"
              >
                <template #prefix>
                  <el-icon><Search /></el-icon>
                </template>
              </el-input>
              <el-select v-model="selectedCategory" placeholder="选择分类" clearable @change="handleSearch" class="filter-select">
                <el-option
                  v-for="item in categoryOptions"
                  :key="item.value"
                  :label="item.label"
                  :value="item.value"
                />
              </el-select>
              <el-select v-model="selectedSeason" placeholder="选择季节" clearable @change="handleSearch" class="filter-select">
                <el-option
                  v-for="item in seasonOptions"
                  :key="item.value"
                  :label="item.label"
                  :value="item.value"
                />
              </el-select>
            </div>
          </div>
        </div>

        <!-- 衣物列表 -->
        <div class="clothes-list">
          <el-empty v-if="filteredClothes.length === 0" description="没有找到衣物" />
          <div v-else class="clothes-grid">
            <div
              v-for="item in filteredClothes"
              :key="item.id"
              class="clothes-item"
              :class="{ 'selected': selectedClothes.some(c => c.id === item.id) }"
              @click="handleClothesClick(item)"
            >
              <el-image
                :src="item.image_url"
                fit="cover"
                class="clothes-image"
                :preview-src-list="[item.image_url]"
                :initial-index="0"
                preview-teleported
                :hide-on-click-modal="false"
                @click.stop
              >
                <template #error>
                  <div class="image-placeholder">
                    <el-icon><Picture /></el-icon>
                  </div>
                </template>
              </el-image>
              <div class="clothes-info">
                <div class="clothes-name">{{ item.name }}</div>
                <div class="clothes-tags">
                  <el-tag size="small" type="info">{{ item.category }}</el-tag>
                  <el-tag size="small" :type="getSeasonType(item.season)">
                    {{ getSeasonName(item.season) }}
                  </el-tag>
                </div>
              </div>
              <div class="selection-indicator">
                <el-icon v-if="selectedClothes.some(c => c.id === item.id)"><Check /></el-icon>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 右侧对话区域 -->
      <div class="chat-section">
        <div class="chat-header">
          <h3>AI搭配助手</h3>
          <div class="header-actions">
            <el-tooltip content="清空对话" placement="top">
              <el-button type="primary" circle @click="clearChat" :disabled="chatMessages.length === 0">
                <el-icon><Delete /></el-icon>
              </el-button>
            </el-tooltip>
          </div>
        </div>

        <!-- 聊天消息区域 -->
        <div class="chat-messages" ref="chatMessagesRef">
          <div v-if="chatMessages.length === 0" class="empty-chat">
            <el-empty description="选择衣物后，开始与AI助手对话">
              <template #image>
                <el-icon :size="60" color="#409EFF"><ChatDotRound /></el-icon>
              </template>
            </el-empty>
          </div>
          <div v-else class="message-list">
            <div
              v-for="(message, index) in chatMessages"
              :key="index"
              class="message-item"
              :class="{ 'user-message': message.role === 'user', 'ai-message': message.role === 'assistant' }"
            >
              <div class="message-avatar">
                <el-avatar :size="40" :icon="message.role === 'user' ? 'User' : 'Service'" :class="message.role === 'user' ? 'user-avatar' : 'ai-avatar'" />
              </div>
              <div class="message-content">
                <template v-if="message.role === 'user'">
                  <span>{{ message.content }}</span>
                  <div v-if="message.image" class="message-image">
                    <el-image
                      :src="message.image"
                      fit="cover"
                      :preview-src-list="[message.image]"
                    >
                      <template #error>
                        <div class="image-error">
                          <el-icon><Picture /></el-icon>
                          <span>图片加载失败</span>
                        </div>
                      </template>
                    </el-image>
                  </div>
                </template>
                <template v-else>
                  <div v-if="typeof message.content === 'object'" class="ai-formatted-response">
                    <!-- 问题回答部分 -->
                    <div v-if="message.content.问题回答" class="response-section">
                      <h4>AI 回答</h4>
                      <p>{{ message.content.问题回答 }}</p>
                    </div>
                    
                    <!-- 推荐图片部分 -->
                    <div v-if="message.content.推荐图片 && message.content.推荐图片.length > 0" class="response-section">
                      <h4>相关图片</h4>
                      <div class="image-grid">
                        <div v-for="(img, index) in message.content.推荐图片" :key="index" class="image-item">
                          <el-image
                            :src="img"
                            fit="cover"
                            :preview-src-list="message.content.推荐图片"
                            :initial-index="index"
                            preview-teleported
                            :hide-on-click-modal="false"
                          >
                            <template #error>
                              <div class="image-error">
                                <el-icon><Picture /></el-icon>
                                <span>图片加载失败</span>
                              </div>
                            </template>
                          </el-image>
                        </div>
                      </div>
                    </div>
                  </div>
                  <span v-else>{{ message.content }}</span>
                  <div v-if="message.image" class="message-image">
                    <el-image
                      :src="message.image"
                      fit="cover"
                      :preview-src-list="[message.image]"
                    >
                      <template #error>
                        <div class="image-error">
                          <el-icon><Picture /></el-icon>
                          <span>图片加载失败</span>
                        </div>
                      </template>
                    </el-image>
                  </div>
                </template>
                <div class="message-time">{{ formatTime(message.timestamp) }}</div>
              </div>
            </div>
            
            <!-- 等待回答的加载状态 -->
            <div v-if="isLoading" class="message-item ai-message loading-message">
              <div class="message-avatar">
                <el-avatar :size="40" icon="Service" class="ai-avatar" />
              </div>
              <div class="message-content">
                <div class="loading-message">
                  <el-icon class="is-loading"><Loading /></el-icon>
                  <span>正在思考中...</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- 输入区域 -->
        <div class="chat-input">
          <div class="upload-area" v-if="!uploadedImage">
            <el-upload
              class="image-uploader"
              action="#"
              :http-request="handleImageUpload"
              :show-file-list="false"
              accept=".jpg,.jpeg,.png"
              :disabled="isUploading"
            >
              <div class="upload-content" :class="{ 'is-uploading': isUploading }">
                <template v-if="isUploading">
                  <el-progress type="circle" :percentage="uploadProgress" :width="50" />
                  <span class="upload-text">上传中...</span>
                </template>
                <template v-else>
                  <div class="upload-icon-wrapper">
                    <el-icon class="upload-icon"><Picture /></el-icon>
                  </div>
                  <div class="upload-text">
                    <span class="primary-text">点击或拖拽图片上传</span>
                    <span class="secondary-text">支持 JPG/PNG 格式</span>
                  </div>
                </template>
              </div>
            </el-upload>
          </div>
          <div v-else class="uploaded-image-preview">
            <el-image
              :src="uploadedImage"
              fit="cover"
              class="preview-image"
            >
              <template #error>
                <div class="image-error">
                  <el-icon><Picture /></el-icon>
                  <span>加载失败</span>
                </div>
              </template>
            </el-image>
            <div class="preview-actions">
              <el-button
                type="danger"
                circle
                size="small"
                class="remove-image"
                @click="removeImage"
              >
                <el-icon><Delete /></el-icon>
              </el-button>
            </div>
          </div>
          <el-input
            v-model="userInput"
            type="textarea"
            :rows="3"
            placeholder="输入您的问题，例如：这些衣物适合什么场合？如何搭配？"
            @keyup.enter.ctrl="sendMessage"
            resize="none"
            class="message-input"
          />
          <div class="input-actions">
            <div class="selected-count" v-if="selectedClothes.length > 0">
              <el-tag type="success" effect="plain" class="selected-tag">
                已选择 {{ selectedClothes.length }} 件衣物
              </el-tag>
            </div>
            <el-button type="primary" @click="sendMessage" :loading="isLoading" class="send-button">
              <el-icon v-if="!isLoading"><Position /></el-icon>
              <span>{{ isLoading ? '发送中...' : '发送' }}</span>
            </el-button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, nextTick, watch } from 'vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'
import { debounce } from 'lodash-es'
import {
  Search,
  Picture,
  Check,
  User,
  Service,
  Delete,
  ChatDotRound,
  Position,
  Loading,
  Plus,
  Upload,
  Select
} from '@element-plus/icons-vue'
import type { ClothesItem, ChatMessage, RecommendRequest } from '@/types'
import { useRouter } from 'vue-router'

// 设置 axios 默认配置
axios.defaults.baseURL = import.meta.env.VITE_API_BASE_URL || ''

// 衣物列表
const clothesList = ref<ClothesItem[]>([])
// 选中的衣物
const selectedClothes = ref<ClothesItem[]>([])
// 搜索关键词
const searchKeyword = ref('')
// 选中的分类
const selectedCategory = ref('')
// 选中的季节
const selectedSeason = ref('')
// 聊天消息
const chatMessages = ref<ChatMessage[]>([])
// 用户输入
const userInput = ref('')
// 是否正在发送消息
const isLoading = ref(false)
const chatMessagesRef = ref<HTMLElement | null>(null)

// 添加上传图片相关的状态
const uploadedImage = ref('')
const isUploading = ref(false)

// 添加上传进度
const uploadProgress = ref(0)

// 分类选项
const categoryOptions = [
 { label: '上装', value: '上装' },
  { label: '下装', value: '下装' },
  { label: '套装', value: '套装' }
]

const seasonOptions = [
  { label: '春秋季', value: 'spring_and_autumn' },
  { label: '夏季', value: 'summer' },
  { label: '冬季', value: 'winter' },
  { label: '四季通用', value: 'all_season' }
]

// 计算属性：过滤后的衣物列表
const filteredClothes = computed(() => {
  let result = [...clothesList.value]
  
  // 关键词搜索
  if (searchKeyword.value) {
    const keyword = searchKeyword.value.toLowerCase()
    result = result.filter(item => 
      item.name.toLowerCase().includes(keyword) || 
      (item.description && item.description.toLowerCase().includes(keyword))
    )
  }
  
  // 分类筛选
  if (selectedCategory.value) {
    result = result.filter(item => item.category === selectedCategory.value)
  }
  
  // 季节筛选
  if (selectedSeason.value) {
    result = result.filter(item => item.season === selectedSeason.value)
  }
  
  return result
})

// 获取衣物列表
const getClothesList = async () => {
  try {
    const userId = localStorage.getItem('userId')
    if (!userId) {
      ElMessage.warning('请先登录')
      router.push('/login')
      return
    }
    const res = await axios.get('/api/clothes', {
      params: {
        user_id: userId,
        keyword: searchKeyword.value,
        category: selectedCategory.value,
        season: selectedSeason.value
      }
    })
    if (res.data.code === 200) {
      clothesList.value = res.data.data
    } else {
      ElMessage.error(res.data.message || '获取衣物列表失败')
    }
  } catch (error) {
    console.error('获取衣物列表失败:', error)
    ElMessage.error('获取衣物列表失败')
  }
}

// 处理搜索和筛选
const handleSearch = debounce(() => {
  console.log('搜索条件变化:', {
    keyword: searchKeyword.value,
    category: selectedCategory.value,
    season: selectedSeason.value
  })
  getClothesList()
}, 300)

// 选择/取消选择衣物
const toggleSelectClothes = (item: ClothesItem) => {
  const index = selectedClothes.value.findIndex(c => c.id === item.id)
  if (index === -1) {
    selectedClothes.value.push(item)
  } else {
    selectedClothes.value.splice(index, 1)
  }
}

// 获取季节类型
const getSeasonType = (season: string) => {
  const types: Record<string, string> = {
    'spring_and_autumn': 'success',
    'summer': 'warning',
    'winter': 'danger',
    'all_season': 'info'
  }
  return types[season] || 'info'
}

// 获取季节名称
const getSeasonName = (season: string) => {
  const seasonMap: Record<string, string> = {
    'spring_and_autumn': '春秋季',
    'summer': '夏季',
    'winter': '冬季',
    'all_season': '四季通用'
  }
  return seasonMap[season] || season
}

// 修改图片上传处理函数
const handleImageUpload = async (options: any) => {
  try {
    const file = options.file
    if (!file) {
      ElMessage.error('请选择图片文件')
      return
    }

    // 验证文件类型和大小
    const isImage = file.type.startsWith('image/')
    const isLt2M = file.size / 1024 / 1024 < 2

    if (!isImage) {
      ElMessage.error('只能上传图片文件!')
      return
    }
    if (!isLt2M) {
      ElMessage.error('图片大小不能超过 2MB!')
      return
    }

    isUploading.value = true
    uploadProgress.value = 0

    // 创建 FormData
    const formData = new FormData()
    formData.append('file', file)
    // 通过后端代理上传到图床，避免在前端暴露图床 token
    const response = await axios.post('/api/upload-to-imgbed', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      },
      onUploadProgress: (progressEvent) => {
        if (progressEvent.total) {
          uploadProgress.value = Math.round((progressEvent.loaded * 100) / progressEvent.total)
        }
      }
    })

    if (response.status === 200 && !response.data.err) {
      uploadedImage.value = response.data.url
      ElMessage.success('图片上传成功')
    } else {
      throw new Error(response.data.msg || '上传失败')
    }
  } catch (error) {
    console.error('上传图片失败:', error)
    ElMessage.error('上传失败，请重试')
  } finally {
    isUploading.value = false
    uploadProgress.value = 0
  }
}

// 移除已上传的图片
const removeImage = () => {
  uploadedImage.value = ''
}

// 修改发送消息函数
const sendMessage = async () => {
  if (!userInput.value.trim()) {
    ElMessage.warning('请输入内容')
    return
  }
  
  // 添加用户消息
  const userMessage: ChatMessage = {
    role: 'user',
    content: userInput.value,
    timestamp: new Date(),
    image: uploadedImage.value
  }
  chatMessages.value.push(userMessage)
  
  // 清空输入框
  const message = userInput.value
  userInput.value = ''
  
  // 滚动到底部
  await nextTick()
  scrollToBottom()
  
  // 显示加载状态
  isLoading.value = true
  
  try {
    const userId = localStorage.getItem('userId')
    if (!userId) {
      ElMessage.warning('请先登录')
      router.push('/login')
      return
    }
    
    // 准备请求数据
    const requestData = {
      question: message,
      user_id: userId,
      image_url: uploadedImage.value,
      clothes_images: [] as string[]  // 添加衣物图片数组
    }

    // 如果选择了衣物，添加衣物信息和图片链接
    if (selectedClothes.value.length > 0) {
      requestData.clothes = selectedClothes.value.map(item => ({
        id: item.id,
        name: item.name,
        category: item.category,
        style: item.style,
        color: item.colorName || item.color,
        season: getSeasonName(item.season),
        material: item.material,
        occasions: item.occasions || [],
        description: item.description
      }))
      // 添加所有选中衣物的图片链接
      requestData.clothes_images = selectedClothes.value.map(item => item.image_url)
    }
    
    // 发送请求到后端
    const response = await axios.post('/api/recommend', requestData)
    
    if (response.data.code === 200) {
      if (response.data.message) {
        // 如果有message字段，说明是提示信息
        ElMessage.warning(response.data.message)
        // 添加AI提示消息
        chatMessages.value.push({
          role: 'assistant',
          content: response.data.message,
          timestamp: new Date()
        })
      } else {
        // 正常的AI回复
        const assistantMessage: ChatMessage = {
          role: 'assistant',
          content: response.data.data,
          timestamp: new Date(),
          image: response.data.image_url
        }
        chatMessages.value.push(assistantMessage)
      }
      
      // 清除已上传的图片
      uploadedImage.value = ''
    } else {
      throw new Error(response.data.message || '获取回复失败')
    }
  } catch (error) {
    console.error('获取AI回复失败:', error)
    
    // 添加错误消息
    chatMessages.value.push({
      role: 'assistant',
      content: error.message || '抱歉，我遇到了一些问题，无法回答您的问题。请稍后再试。',
      timestamp: new Date()
    })
    
    // 显示错误提示
    ElMessage.error(error.message || '获取回复失败，请重试')
  } finally {
    isLoading.value = false
    
    // 滚动到底部
    await nextTick()
    scrollToBottom()
  }
}

// 清空对话
const clearChat = () => {
  chatMessages.value = []
}

// 滚动到底部
const scrollToBottom = () => {
  if (chatMessagesRef.value) {
    chatMessagesRef.value.scrollTop = chatMessagesRef.value.scrollHeight
  }
}

// 格式化时间
const formatTime = (timestamp: Date) => {
  if (!timestamp) return ''
  const date = new Date(timestamp)
  return `${date.getHours().toString().padStart(2, '0')}:${date.getMinutes().toString().padStart(2, '0')}`
}

// 监听消息变化，自动滚动到底部
watch(chatMessages, () => {
  nextTick(() => {
    scrollToBottom()
  })
})

// 组件挂载时获取衣物列表
onMounted(() => {
  getClothesList()
})

// 处理衣物点击
const handleClothesClick = (item: ClothesItem) => {
  // 如果点击的是图片，不触发选择
  if (event?.target instanceof HTMLElement && event.target.closest('.el-image')) {
    return
  }
  toggleSelectClothes(item)
}

// 格式化消息内容
const formatMessage = (content: string) => {
  return content
    .replace(/\n/g, '<br>')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    .replace(/`(.*?)`/g, '<code>$1</code>')
}

// 添加全选相关的状态和方法
const isAllSelected = computed(() => {
  return filteredClothes.value.length > 0 && 
         filteredClothes.value.every(item => 
           selectedClothes.value.some(selected => selected.id === item.id)
         )
})

// 全选/取消全选
const toggleSelectAll = () => {
  if (isAllSelected.value) {
    // 取消全选
    selectedClothes.value = selectedClothes.value.filter(item => 
      !filteredClothes.value.some(filtered => filtered.id === item.id)
    )
  } else {
    // 全选当前筛选结果
    const newSelected = new Set([...selectedClothes.value])
    filteredClothes.value.forEach(item => {
      if (!selectedClothes.value.some(selected => selected.id === item.id)) {
        newSelected.add(item)
      }
    })
    selectedClothes.value = Array.from(newSelected)
  }
}

// 添加衣物按钮处理函数
const handleAddClothes = () => {
  showAddDialog.value = true
}
</script>

<style scoped>
.recommend-container {
  padding: 20px;
  height: 100%;
  display: flex;
  flex-direction: column;
  background-color: #f5f7fa;
}

.page-header {
  margin-bottom: 20px;
  text-align: center;
  padding: 20px 0;
  background: linear-gradient(135deg, #2d5a9d 0%, #1e3c6e 100%);
  border-radius: 8px;
  color: white;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.page-header h2 {
  font-size: 28px;
  color: white;
  margin-bottom: 8px;
  font-weight: 600;
}

.page-header p {
  font-size: 16px;
  color: rgba(255, 255, 255, 0.9);
}

/* 调整主要内容区域的宽度分布 */
.main-content {
  display: flex;
  flex: 1;
  gap: 20px;
  height: calc(100vh - 180px);
  min-height: 500px;
  overflow: hidden;
}

/* 减小左侧衣物选择区的宽度 */
.clothes-selection {
  width: 35%; /* 从40%减小到35% */
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  transition: all 0.3s;
  min-width: 280px; /* 减小最小宽度，从320px减小到280px */
}

.clothes-selection:hover {
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.12);
}

.section-title {
  padding: 15px;
  border-bottom: 1px solid #ebeef5;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.section-title h3 {
  margin: 0;
  font-size: 18px;
  color: #303133;
  font-weight: 600;
}

.operation-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
  padding: 0 6px;
  margin-bottom: 20px;
}

.left {
  display: flex;
  gap: 8px;
  align-items: center;
}

.right {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.search-input {
  width: 180px;
}

.filter-select {
  width: 140px;
}

.clothes-list {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 12px;
}

/* 调整衣物网格以适应更小的空间 */
.clothes-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); /* 减小每个项目的大小 */
  gap: 12px;
  padding: 10px;
  width: 100%;
}

/* 优化衣物项目大小 */
.clothes-item {
  position: relative;
  border-radius: 12px;
  overflow: hidden;
  background: white;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  transition: all 0.3s;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 250px; /* 略微减小高度 */
}

.clothes-item:hover {
  transform: translateY(-5px);
  box-shadow: 0 5px 15px rgba(0, 0, 0, 0.2);
}

.clothes-item.selected {
  border: 2px solid #2d5a9d;
  box-shadow: 0 0 0 2px rgba(45, 90, 157, 0.2);
}

.clothes-image {
  width: 100%;
  height: 160px; /* 略微减小高度 */
  object-fit: cover;
  transition: all 0.3s;
}

/* 优化衣物信息区域 */
.clothes-info {
  padding: 8px;
  background: white;
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.clothes-name {
  font-size: 12px;
  font-weight: 500;
  color: #303133;
  margin: 0;
  line-height: 1.3;
  height: 2.6em;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.clothes-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 3px;
  margin-top: auto;
}

.clothes-tags :deep(.el-tag) {
  padding: 0 6px;
  height: 20px;
  line-height: 18px;
  font-size: 10px;
}

.selection-indicator {
  position: absolute;
  top: 8px;
  right: 8px;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: rgba(45, 90, 157, 0.9);
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
  z-index: 1;
  transform: scale(1);
}

.image-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f5f7fa;
  color: #909399;
}

.image-placeholder .el-icon {
  font-size: 32px;
}

/* 增加右侧聊天区域的宽度 */
.chat-section {
  width: 65%; /* 从60%增加到65% */
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  transition: all 0.3s;
  min-width: 400px;
}

.chat-section:hover {
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.12);
}

/* 调整聊天头部，减少不必要的空间 */
.chat-header {
  padding: 10px 15px;
  border-bottom: 1px solid #ebeef5;
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: linear-gradient(to right, #f5f7fa, white);
}

.chat-header h3 {
  margin: 0;
  font-size: 18px;
  color: #303133;
  font-weight: 600;
}

.header-actions {
  display: flex;
  gap: 10px;
}

/* 优化聊天消息区域，增加高度以显示更多内容 */
.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 12px 15px; /* 轻微减小内边距 */
  display: flex;
  flex-direction: column;
  background-color: #f9fafc;
  max-height: calc(100vh - 330px); /* 设置最大高度以确保可以显示更多消息 */
}

.empty-chat {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

/* 优化消息条目，减少不必要的间距 */
.message-list {
  display: flex;
  flex-direction: column;
  gap: 12px; /* 从15px减小到12px，使消息更紧凑 */
}

.message-item {
  display: flex;
  gap: 10px;
  max-width: 80%;
  animation: fadeIn 0.3s ease-in-out;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

.user-message {
  align-self: flex-end;
  flex-direction: row-reverse;
}

.ai-message {
  align-self: flex-start;
}

.message-avatar {
  flex-shrink: 0;
}

.user-avatar {
  background-color: #2d5a9d;
}

.ai-avatar {
  background-color: #67c23a;
}

/* 优化消息内容显示 */
.message-content {
  background: #f5f7fa;
  padding: 10px 14px; /* 减小内边距 */
  border-radius: 12px;
  position: relative;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.05);
  max-width: 100%; /* 确保内容不会溢出 */
}

.user-message .message-content {
  background: #ecf5ff;
  border-bottom-right-radius: 4px;
}

.ai-message .message-content {
  border-bottom-left-radius: 4px;
}

.message-text {
  font-size: 14px;
  color: #303133;
  line-height: 1.6;
}

.loading-message {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #909399;
}

.loading-message .el-icon {
  font-size: 16px;
}

.message-time {
  font-size: 12px;
  color: #909399;
  margin-top: 5px;
  text-align: right;
}

/* 优化输入区域，减少不必要的高度 */
.chat-input {
  padding: 12px;
  border-top: 1px solid #ebeef5;
  background-color: white;
}

.message-input {
  border-radius: 8px;
  overflow: hidden;
}

.message-input :deep(.el-textarea__inner) {
  border-radius: 8px;
  padding: 12px;
  font-size: 14px;
  resize: none;
  transition: all 0.3s;
}

.message-input :deep(.el-textarea__inner:focus) {
  box-shadow: 0 0 0 2px rgba(45, 90, 157, 0.2);
}

.input-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 10px;
}

.selected-tag {
  font-size: 13px;
  padding: 0 10px;
  height: 28px;
  line-height: 26px;
}

.send-button {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 10px 20px;
  border-radius: 8px;
  font-weight: 500;
  transition: all 0.3s;
}

.send-button:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(45, 90, 157, 0.3);
}

:deep(.el-tag) {
  border-radius: 4px;
}

:deep(.el-button--primary) {
  background-color: #2d5a9d;
  border-color: #2d5a9d;
}

:deep(.el-button--primary:hover) {
  background-color: #3a6ab8;
  border-color: #3a6ab8;
}

:deep(.el-empty__image) {
  display: flex;
  justify-content: center;
  align-items: center;
}

:deep(.el-select .el-input__wrapper) {
  box-shadow: 0 0 0 1px #dcdfe6 inset;
}

:deep(.el-select .el-input__wrapper:hover) {
  box-shadow: 0 0 0 1px #c0c4cc inset;
}

:deep(.el-select .el-input__wrapper.is-focus),
:deep(.el-input__wrapper.is-focus) {
  box-shadow: 0 0 0 2px #2d5a9d inset !important;
  border: 1.5px solid #2d5a9d !important;
}

:deep(.el-input__wrapper) {
  border-radius: 6px;
  transition: box-shadow 0.2s, border 0.2s;
}

/* Markdown 样式 */
.markdown-body {
  line-height: 1.6;
}

.markdown-body code {
  background-color: #f5f7fa;
  padding: 2px 4px;
  border-radius: 4px;
  font-family: monospace;
}

.markdown-body strong {
  font-weight: 600;
}

.markdown-body em {
  font-style: italic;
}

/* 全屏预览样式 */
:deep(.el-image-viewer__wrapper) {
  z-index: 2100;
}

:deep(.el-image-viewer__btn) {
  color: #fff;
  font-size: 24px;
}

:deep(.el-image-viewer__actions) {
  background-color: rgba(45, 90, 157, 0.9);
  border-radius: 20px;
  padding: 8px 20px;
}

:deep(.el-image-viewer__actions__inner) {
  display: flex;
  gap: 20px;
}

:deep(.el-image-viewer__close) {
  top: 40px;
  right: 40px;
  color: #2d5a9d;
  background-color: rgba(255, 255, 255, 0.9);
  border-radius: 50%;
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.3s;
}

:deep(.el-image-viewer__close:hover) {
  background-color: #2d5a9d;
  color: #fff;
}

:deep(.el-image-viewer__canvas) {
  background-color: rgba(0, 0, 0, 0.9);
}

:deep(.el-image-viewer__actions__inner i) {
  color: #fff;
  font-size: 20px;
}

:deep(.el-image-viewer__actions__inner i:hover) {
  color: #ecf5ff;
}

/* 优化上传区域，大幅减少垂直空间占用 */
.upload-area {
  margin-bottom: 8px;
  border: 1px dashed #e4e7ed;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.3s;
  background: #fafafa;
}

.upload-area:hover {
  border-color: #2d5a9d;
  background: rgba(45, 90, 157, 0.05);
}

.upload-content {
  padding: 10px 12px; /* 大幅减小内边距 */
  text-align: center;
  display: flex;
  flex-direction: row; /* 改为水平布局 */
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.upload-content.is-uploading {
  padding: 16px;
}

.upload-icon-wrapper {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: rgba(45, 90, 157, 0.1);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 0;
}

.upload-icon {
  font-size: 16px;
  color: #2d5a9d;
}

.upload-text {
  display: flex;
  flex-direction: column;
  gap: 0;
  text-align: left;
}

.primary-text {
  font-size: 14px;
  color: #303133;
  font-weight: 500;
}

.secondary-text {
  font-size: 12px;
  color: #909399;
}

.uploaded-image-preview {
  position: relative;
  margin-bottom: 15px;
  width: 120px;
  height: 120px;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
  transition: all 0.3s;
}

.uploaded-image-preview:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.15);
}

.preview-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.preview-actions {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  transition: opacity 0.3s;
}

.uploaded-image-preview:hover .preview-actions {
  opacity: 1;
}

.remove-image {
  background: rgba(255, 255, 255, 0.9);
  border: none;
}

.remove-image:hover {
  background: #fff;
  transform: scale(1.1);
}

.image-error {
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #909399;
  background: #f5f7fa;
  gap: 8px;
}

.message-image {
  margin-top: 10px;
  max-width: 200px;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
}

.message-image .el-image {
  width: 100%;
  height: 150px;
  cursor: pointer;
  transition: transform 0.3s;
}

.message-image .el-image:hover {
  transform: scale(1.02);
}

/* 添加进度条样式 */
:deep(.el-progress) {
  margin-bottom: 8px;
}

:deep(.el-progress__text) {
  color: #2d5a9d;
}

:deep(.el-progress-circle) {
  transform: scale(0.8);
}

/* 优化消息显示样式 */
.ai-formatted-response {
  display: flex;
  flex-direction: column;
  gap: 12px; /* 减小间距 */
}

.response-section {
  background: #f8f9fa;
  border-radius: 8px;
  padding: 10px; /* 减小内边距 */
}

.response-section h4 {
  color: #2d5a9d;
  margin: 0 0 8px 0;
  font-size: 16px;
  font-weight: 600;
}

.response-section p {
  margin: 0;
  line-height: 1.6;
  color: #303133;
}

.image-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap: 12px;
  margin-top: 8px;
}

.image-item {
  position: relative;
  aspect-ratio: 1;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
  cursor: pointer;
  transition: all 0.3s;
}

.image-item:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.15);
}

.image-name {
  padding: 8px;
  background: rgba(255, 255, 255, 0.9);
  font-size: 12px;
  color: #303133;
  text-align: center;
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  backdrop-filter: blur(4px);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.select-all-button {
  display: flex;
  align-items: center;
  gap: 4px;
}

/* 针对Mac Chrome的滚动条优化 */
.clothes-list::-webkit-scrollbar {
  width: 8px;
}

.clothes-list::-webkit-scrollbar-track {
  background: #f1f1f1;
  border-radius: 4px;
}

.clothes-list::-webkit-scrollbar-thumb {
  background: #c1c1c1;
  border-radius: 4px;
}

.clothes-list::-webkit-scrollbar-thumb:hover {
  background: #a8a8a8;
}

/* 针对Mac高分辨率屏幕的特定修复 */
@media screen and (-webkit-min-device-pixel-ratio: 2) {
  .clothes-grid {
    grid-template-columns: repeat(2, 1fr); /* 保持两列 */
  }
  
  .clothes-item {
    min-height: 190px;
  }
  
  .clothes-image {
    height: 110px;
  }
}

/* 针对特定显示器分辨率的调整 - 特别适用于M1 Air */
@media (min-width: 1280px) and (max-width: 1440px) {
  .clothes-selection {
    width: 32%;
  }
  
  .chat-section {
    width: 68%;
  }
  
  .clothes-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

/* 更大屏幕上保持良好的比例 */
@media (min-width: 1441px) {
  .clothes-selection {
    width: 30%;
  }
  
  .chat-section {
    width: 70%;
  }
}

/* 针对不同屏幕尺寸的响应式布局优化 */
@media (max-width: 1280px) {
  .main-content {
    gap: 16px;
  }
  
  .operation-bar {
    padding: 0 4px;
  }
  
  .clothes-grid {
    grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
    gap: 12px;
    padding: 10px;
  }
  
  .search-input {
    width: 160px;
  }
  
  .filter-select {
    width: 130px;
  }
}

@media (max-width: 1024px) {
  .clothes-selection {
    width: 38%;
    min-width: 280px;
  }
  
  .chat-section {
    width: 62%;
    min-width: 380px;
  }
  
  .clothes-grid {
    grid-template-columns: repeat(auto-fill, minmax(130px, 1fr));
    gap: 10px;
  }
  
  .clothes-item {
    min-height: 240px;
  }
  
  .clothes-image {
    height: 150px;
  }
}

/* 针对特殊分辨率的修复 */
@media (min-width: 1400px) and (max-width: 1600px) {
  .clothes-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

/* 主内容区自适应 */
@media (max-width: 900px) {
  .main-content {
    flex-direction: column;
    gap: 12px;
    height: auto;
    min-height: 0;
  }
  .clothes-selection,
  .chat-section {
    width: 100%;
    min-width: 0;
    margin-bottom: 12px;
  }
}

/* 衣物卡片自适应 */
@media (max-width: 700px) {
  .operation-bar {
    flex-direction: column;
    align-items: stretch;
    gap: 8px;
  }
  .operation-bar .right {
    flex-wrap: wrap;
    gap: 8px;
    width: 100%;
  }
  .operation-bar .right > * {
    flex: 1 1 120px;
    min-width: 0;
    margin-bottom: 4px;
  }
  .search-input,
  .filter-select {
    width: 100% !important;
    min-width: 0;
  }
  .clothes-grid {
    grid-template-columns: repeat(2, 1fr);
    gap: 8px;
    padding: 6px;
  }
  .clothes-image {
    height: 100px;
  }
}

/* 聊天输入区、按钮等自适应 */
@media (max-width: 600px) {
  .chat-input {
    padding: 8px;
  }
  .send-button {
    padding: 8px 12px;
    font-size: 14px;
  }
  .selected-tag {
    font-size: 12px;
    height: 24px;
    line-height: 22px;
  }
  .message-input :deep(.el-textarea__inner) {
    font-size: 13px;
    padding: 8px;
  }
}

/* 聊天消息区自适应 */
@media (max-width: 500px) {
  .chat-messages {
    padding: 6px;
  }
  .message-content {
    padding: 8px 10px;
    font-size: 13px;
  }
  .message-item {
    max-width: 98%;
  }
  .clothes-info {
    padding: 6px;
  }
  .clothes-name {
    font-size: 12px;
  }
}

/* 顶部标题自适应 */
@media (max-width: 600px) {
  .page-header {
    padding: 10px 0;
  }
  .page-header h2 {
    font-size: 20px;
  }
  .page-header p {
    font-size: 13px;
  }
}

@media (max-width: 900px) {
  .chat-section {
    width: 100% !important;
    min-width: 0;
    border-radius: 8px !important;
    box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
    margin-bottom: 0;
  }
}

@media (max-width: 700px) {
  .chat-section {
    border-radius: 0 !important;
    box-shadow: none !important;
  }
}
</style>
