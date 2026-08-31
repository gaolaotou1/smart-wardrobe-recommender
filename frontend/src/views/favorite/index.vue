<template>
  <div class="favorite-container">
    <div class="header">
      <div class="header-left">
        <h2>我的穿搭</h2>
        <el-input
          v-model="searchKeyword"
          placeholder="搜索穿搭名称或描述"
          class="search-input"
          clearable
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
      </div>
      <el-button type="primary" @click="openCreateDialog">
        <el-icon><Plus /></el-icon>创建穿搭
      </el-button>
    </div>

    <!-- 穿搭列表 -->
    <div v-if="filteredOutfitList.length > 0" class="outfit-grid">
      <el-card
        v-for="outfit in filteredOutfitList"
        :key="outfit.id"
        class="outfit-card"
        shadow="hover"
      >
        <div class="image-wrapper">
          <el-image
            :src="outfit.image_url"
            fit="cover"
            :preview-src-list="[outfit.image_url]"
            class="outfit-image"
          >
            <template #error>
              <div class="image-placeholder">
                <el-icon><Picture /></el-icon>
              </div>
            </template>
          </el-image>
          <div class="image-overlay">
            <el-button-group>
              <el-button type="primary" @click="handleEdit(outfit)" class="action-button">
                <el-icon><Edit /></el-icon>
              </el-button>
              <el-button type="danger" @click="handleDelete(outfit.id)" class="action-button">
                <el-icon><Delete /></el-icon>
              </el-button>
            </el-button-group>
          </div>
        </div>
        <div class="outfit-info">
          <h3>{{ outfit.name }}</h3>
          <p class="description">{{ outfit.description }}</p>
          <div class="clothes-list">
            <div v-for="item in outfit.clothes" :key="item.id" class="clothes-item">
              <el-image
                :src="item.image_url"
                fit="cover"
                class="clothes-thumbnail"
              >
                <template #error>
                  <div class="thumbnail-placeholder">
                    <el-icon><Picture /></el-icon>
                  </div>
                </template>
              </el-image>
              <span class="clothes-name">{{ item.name }}</span>
            </div>
          </div>
        </div>
      </el-card>
    </div>
    <el-empty v-else description="暂无匹配的穿搭" />

    <!-- 创建/编辑穿搭对话框 -->
    <el-dialog
      v-model="showCreateDialog"
      :title="editingOutfit ? '编辑穿搭' : '创建穿搭'"
      width="800px"
      class="create-dialog"
      :close-on-click-modal="false"
      @close="handleCloseDialog"
    >
      <div class="dialog-content">
        <el-form
          ref="formRef"
          :model="outfitForm"
          :rules="rules"
          label-width="80px"
          class="outfit-form"
        >
          <el-form-item label="名称" prop="name">
            <el-input 
              v-model="outfitForm.name" 
              placeholder="请输入穿搭名称"
              :prefix-icon="Edit"
            />
          </el-form-item>
          <el-form-item label="描述" prop="description">
            <el-input
              v-model="outfitForm.description"
              type="textarea"
              :rows="3"
              placeholder="请输入穿搭描述"
              resize="none"
            />
          </el-form-item>
          <el-form-item label="封面" prop="image_url">
            <div class="image-upload-container">
              <el-upload
                class="avatar-uploader"
                action="#"
                :http-request="handleImageSuccess"
                :show-file-list="false"
                :before-upload="beforeImageUpload"
              >
                <div class="upload-area">
                  <template v-if="outfitForm.image_url">
                    <img :src="outfitForm.image_url" class="avatar" />
                  </template>
                  <div v-else class="upload-placeholder">
                    <template v-if="isUploading">
                      <el-progress 
                        type="circle" 
                        :percentage="uploadProgress"
                        :status="uploadProgress === 100 ? 'success' : ''"
                      />
                      <span class="upload-text">上传中...</span>
                    </template>
                    <template v-else>
                      <el-icon class="upload-icon"><Plus /></el-icon>
                      <span class="upload-text">点击上传封面</span>
                    </template>
                  </div>
                </div>
              </el-upload>
              <div class="image-tips">
                <el-icon><InfoFilled /></el-icon>
                <span>建议上传尺寸为 800x800 的图片</span>
              </div>
            </div>
          </el-form-item>
          <el-form-item label="衣物" class="clothes-form-item">
            <div class="clothes-container">
              <div v-if="selectedClothes.length > 0" class="selected-clothes">
                <div
                  v-for="(item, index) in selectedClothes"
                  :key="item.id"
                  class="selected-item"
                >
                  <el-image
                    :src="item.image_url"
                    fit="cover"
                    class="selected-image"
                  />
                  <div class="item-info">
                    <span class="item-name">{{ item.name }}</span>
                    <el-tag size="small" :type="getTagType(item.category)">{{ item.category }}</el-tag>
                  </div>
                  <el-button
                    type="danger"
                    circle
                    size="small"
                    @click="removeClothes(index)"
                  >
                    <el-icon><Delete /></el-icon>
                  </el-button>
                </div>
              </div>
              <div class="clothes-actions">
                <el-button type="primary" @click="showClothesSelector = true" class="select-clothes-btn">
                  <el-icon><Plus /></el-icon>选择衣物
                </el-button>
                <el-button 
                  v-if="selectedClothes.length > 0" 
                  type="success" 
                  @click="openPreview"
                  class="preview-btn"
                >
                  <el-icon><View /></el-icon>预览效果
                </el-button>
              </div>
            </div>
          </el-form-item>
          <div class="form-footer">
            <el-button @click="handleCloseDialog">取消</el-button>
            <el-button type="primary" @click="handleSubmit" :loading="submitting">
              {{ editingOutfit ? '保存修改' : '创建穿搭' }}
            </el-button>
          </div>
        </el-form>
      </div>
    </el-dialog>

    <!-- 衣物选择器对话框 -->
    <el-dialog
      v-model="showClothesSelector"
      title="选择衣物"
      width="800px"
    >
      <div class="clothes-selector">
        <el-input
          v-model="clothesSearchKeyword"
          placeholder="搜索衣物名称或分类"
          class="clothes-search-input"
          clearable
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
        <div class="clothes-grid">
          <div
            v-for="item in filteredClothes"
            :key="item.id"
            class="clothes-selector-item"
            :class="{ selected: isSelected(item) }"
            @click="toggleClothes(item)"
          >
            <el-image
              :src="item.image_url"
              fit="cover"
              class="selector-image"
            />
            <div class="selector-info">
              <span>{{ item.name }}</span>
              <el-tag size="small">{{ item.category }}</el-tag>
            </div>
          </div>
        </div>
      </div>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="showClothesSelector = false">取消</el-button>
          <el-button type="primary" @click="confirmSelection">确定</el-button>
        </span>
      </template>
    </el-dialog>

    <!-- 预览对话框 -->
    <el-dialog
      v-model="showPreviewDialog"
      title="穿搭预览"
      fullscreen
      :show-close="true"
      :close-on-click-modal="false"
      class="preview-dialog"
    >
      <div class="preview-container">
        <div class="preview-toolbar">
          <div class="toolbar-left">
            <el-button-group>
              <el-button @click="zoomIn" :disabled="selectedItemIndex === -1">
                <el-icon><ZoomIn /></el-icon>
              </el-button>
              <el-button @click="zoomOut" :disabled="selectedItemIndex === -1">
                <el-icon><ZoomOut /></el-icon>
              </el-button>
              <el-button @click="rotateLeft" :disabled="selectedItemIndex === -1">
                <el-icon><RefreshLeft /></el-icon>
              </el-button>
              <el-button @click="rotateRight" :disabled="selectedItemIndex === -1">
                <el-icon><RefreshRight /></el-icon>
              </el-button>
              <el-button @click="resetTransform" :disabled="selectedItemIndex === -1">
                <el-icon><Refresh /></el-icon>
              </el-button>
            </el-button-group>
          </div>
          <div class="toolbar-right">
            <el-button @click="showPreviewDialog = false">返回编辑</el-button>
            <el-button type="primary" @click="savePreview">
              <el-icon><Download /></el-icon>保存图片
            </el-button>
          </div>
        </div>
        <div class="preview-main">
          <div class="preview-canvas" ref="previewCanvas">
            <div 
              v-for="(item, index) in selectedClothes" 
              :key="index"
              class="preview-item"
              :class="{ 'selected': selectedItemIndex === index }"
              :style="getItemStyle(item)"
              @mousedown="startDrag($event, index)"
              @click="selectItem(index)"
            >
              <el-image
                :src="item.image_url"
                fit="contain"
                class="preview-image"
                crossorigin="anonymous"
              />
            </div>
          </div>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { FormInstance } from 'element-plus'
import axios from 'axios'
import {
  Plus,
  Edit,
  Delete,
  Picture,
  Search,
  ZoomIn,
  ZoomOut,
  RefreshLeft,
  RefreshRight,
  Refresh,
  Download,
  InfoFilled,
  View
} from '@element-plus/icons-vue'
import html2canvas from 'html2canvas'
import { useRouter, useRoute } from 'vue-router'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || ''
axios.defaults.baseURL = API_BASE_URL

// 定义类型
interface Clothes {
  id: number
  name: string
  image_url: string
  category: string
  position?: string
}

interface Outfit {
  id: number
  name: string
  description: string
  image_url: string
  clothes: Clothes[]
}

// 表单引用
const formRef = ref<FormInstance>()

// 数据
const outfitList = ref<Outfit[]>([])
const showCreateDialog = ref(false)
const showClothesSelector = ref(false)
const editingOutfit = ref<Outfit | null>(null)
const searchKeyword = ref('')
const clothesList = ref<Clothes[]>([])
const selectedClothes = ref<Clothes[]>([])
const userId = ref('')
const router = useRouter()
const route = useRoute()
const submitting = ref(false)

// 表单数据
const outfitForm = reactive({
  name: '',
  description: '',
  image_url: ''
})

// 表单验证规则
const rules = {
  name: [
    { required: true, message: '请输入穿搭名称', trigger: 'blur' },
    { min: 2, max: 20, message: '长度在 2 到 20 个字符', trigger: 'blur' }
  ],
  description: [
    { max: 200, message: '长度不能超过 200 个字符', trigger: 'blur' }
  ]
}

// 衣物变换状态
const clothesTransform = reactive<Record<number, {
  x: number
  y: number
  scale: number
  rotate: number
  zIndex: number
}>>({})

// 添加上传进度状态
const uploadProgress = ref(0)
const isUploading = ref(false)

// 在 script setup 中添加新的搜索变量
const clothesSearchKeyword = ref('')

// 检查并获取用户ID
const checkUserId = () => {
  const storedUserId = localStorage.getItem('userId')
  if (!storedUserId) {
    ElMessage.warning('请先登录')
    router.push('/login')
    return false
  }
  userId.value = storedUserId
  return true
}

// 获取穿搭列表
const getOutfitList = async () => {
  try {
    const userId = localStorage.getItem('userId')
    const res = await axios.get(`/api/outfits?user_id=${userId}`)
    if (res.data.code === 200) {
      // 处理每个穿搭的衣物列表，确保不重复
      outfitList.value = res.data.data.map(outfit => ({
        ...outfit,
        clothes: Array.from(new Map(outfit.clothes.map(item => [item.id, item])).values())
      }))
    }
  } catch (error) {
    console.error('获取穿搭列表失败:', error)
  }
}

// 获取衣物列表
const getClothesList = async () => {
  try {
    const userId = localStorage.getItem('userId')
    const res = await axios.get(`/api/clothes?user_id=${userId}`)
    if (res.data.code === 200) {
      clothesList.value = res.data.data
    }
  } catch (error) {
    console.error('获取衣物列表失败:', error)
  }
}

// 初始化数据
const initData = async () => {
  const userId = localStorage.getItem('userId')
  if (userId) {
    await Promise.all([getOutfitList(), getClothesList()])
  }
}

// 修改 filteredClothes 计算属性
const filteredClothes = computed(() => {
  if (!clothesSearchKeyword.value) return clothesList.value
  return clothesList.value.filter(item => 
    item.name.toLowerCase().includes(clothesSearchKeyword.value.toLowerCase()) ||
    item.category.toLowerCase().includes(clothesSearchKeyword.value.toLowerCase())
  )
})

// 检查衣物是否已选择
const isSelected = (item) => {
  return selectedClothes.value.some(selected => selected.id === item.id)
}

// 切换衣物选择
const toggleClothes = (item: Clothes) => {
  const index = selectedClothes.value.findIndex(selected => selected.id === item.id)
  if (index === -1) {
    selectedClothes.value.push({
      ...item,
      position: item.category
    })
  } else {
    selectedClothes.value.splice(index, 1)
  }
}

// 移除已选择的衣物
const removeClothes = (index) => {
  selectedClothes.value.splice(index, 1)
}

// 确认选择
const confirmSelection = () => {
  showClothesSelector.value = false
}

// 处理图片上传成功
const handleImageSuccess = async (options) => {
  try {
    const file = options.file
    if (!file) {
      ElMessage.error('请选择图片文件')
      return
    }

    isUploading.value = true
    uploadProgress.value = 0

    const formData = new FormData()
    formData.append('file', file)
    const uploadResponse = await axios.post('/api/upload-to-imgbed', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      },
      onUploadProgress: (progressEvent) => {
        if (progressEvent.total) {
          uploadProgress.value = Math.round((progressEvent.loaded * 100) / progressEvent.total)
        }
      }
    })

    if (uploadResponse.status === 200) {
      if (uploadResponse.data.err === 1) {
        ElMessage.error(uploadResponse.data.msg || '图片上传失败')
        return
      }
      outfitForm.image_url = uploadResponse.data.url
      ElMessage.success('图片上传成功')
    } else {
      ElMessage.error('图片上传失败')
    }
  } catch (error) {
    console.error('上传到图床失败:', error)
    ElMessage.error('图片上传失败')
  } finally {
    isUploading.value = false
    uploadProgress.value = 0
  }
}

// 图片上传前的验证
const beforeImageUpload = (file) => {
  const isImage = file.type.startsWith('image/')
  const isLt2M = file.size / 1024 / 1024 < 2

  if (!isImage) {
    ElMessage.error('只能上传图片文件!')
    return false
  }
  if (!isLt2M) {
    ElMessage.error('图片大小不能超过 2MB!')
    return false
  }

  return true
}

// 重置表单
const resetForm = () => {
  outfitForm.name = ''
  outfitForm.description = ''
  outfitForm.image_url = ''
  selectedClothes.value = []
  editingOutfit.value = null
}

// 打开创建对话框
const openCreateDialog = () => {
  resetForm()
  showCreateDialog.value = true
}

// 处理编辑
const handleEdit = (outfit) => {
  editingOutfit.value = outfit
  outfitForm.name = outfit.name
  outfitForm.description = outfit.description
  outfitForm.image_url = outfit.image_url
  selectedClothes.value = outfit.clothes.map(item => ({
    ...item,
    position: item.position
  }))
  showCreateDialog.value = true
}

// 处理删除
const handleDelete = async (id) => {
  try {
    await ElMessageBox.confirm('确定要删除这个穿搭吗？', '提示', {
      type: 'warning'
    })
    const res = await axios.delete(`/api/outfits/${id}`)
    if (res.data.code === 200) {
      ElMessage.success('删除成功')
      getOutfitList()
    }
  } catch (error) {
    if (error !== 'cancel') {
      console.error('删除穿搭失败:', error)
      ElMessage.error('删除穿搭失败')
    }
  }
}

// 处理提交
const handleSubmit = async () => {
  if (!formRef.value) return
  
  try {
    await formRef.value.validate()
    const submitData = {
      ...outfitForm,
      clothes: selectedClothes.value,
      user_id: localStorage.getItem('userId') || ''
    }
    
    if (editingOutfit.value) {
      const res = await axios.put(`/api/outfits/${editingOutfit.value.id}`, submitData)
      if (res.data.code === 200) {
        ElMessage.success('更新成功')
        showCreateDialog.value = false
        getOutfitList()
      }
    } else {
      const res = await axios.post('/api/outfits', submitData)
      if (res.data.code === 200) {
        ElMessage.success('创建成功')
        showCreateDialog.value = false
        getOutfitList()
      }
    }
  } catch (error) {
    console.error('提交失败:', error)
    ElMessage.error('提交失败')
  }
}

// 预览相关
const showPreviewDialog = ref(false)
const previewCanvas = ref<HTMLElement | null>(null)
const draggingIndex = ref(-1)
const dragStartX = ref(0)
const dragStartY = ref(0)
const selectedItemIndex = ref(-1)
const isDragging = ref(false)

// 初始化衣物变换状态
const initClothesTransform = () => {
  selectedClothes.value.forEach((item, index) => {
    if (!clothesTransform[index]) {
      clothesTransform[index] = {
        x: 0,
        y: 0,
        scale: 1,
        rotate: 0,
        zIndex: index
      }
    }
  })
}

// 监听selectedClothes变化，初始化变换状态
watch(selectedClothes, () => {
  initClothesTransform()
}, { deep: true })

// 选择衣物
const selectItem = (index: number) => {
  if (!isDragging.value) {
    // 将选中的衣物置于顶层
    const maxZIndex = Math.max(...Object.values(clothesTransform).map(t => t.zIndex))
    clothesTransform[selectedItemIndex.value].zIndex = maxZIndex + 1
    selectedItemIndex.value = index
  }
}

// 获取衣物样式
const getItemStyle = (item: Clothes) => {
  const index = selectedClothes.value.indexOf(item)
  const transform = clothesTransform[index] || { x: 0, y: 0, scale: 1, rotate: 0, zIndex: 0 }
  return {
    transform: `translate(calc(-50% + ${transform.x}px), calc(-50% + ${transform.y}px)) scale(${transform.scale}) rotate(${transform.rotate}deg)`,
    position: 'absolute' as const,
    cursor: 'move',
    zIndex: transform.zIndex,
    transition: isDragging.value ? 'none' : 'transform 0.1s'
  }
}

// 开始拖动
const startDrag = (event: MouseEvent, index: number) => {
  event.preventDefault()
  isDragging.value = true
  draggingIndex.value = index
  selectedItemIndex.value = index
  // 将拖动的衣物置于顶层
  const maxZIndex = Math.max(...Object.values(clothesTransform).map(t => t.zIndex))
  clothesTransform[index].zIndex = maxZIndex + 1
  dragStartX.value = event.clientX - clothesTransform[index].x
  dragStartY.value = event.clientY - clothesTransform[index].y
  document.addEventListener('mousemove', onDrag)
  document.addEventListener('mouseup', stopDrag)
}

// 拖动中
const onDrag = (event: MouseEvent) => {
  if (draggingIndex.value === -1) return
  const index = draggingIndex.value
  clothesTransform[index].x = event.clientX - dragStartX.value
  clothesTransform[index].y = event.clientY - dragStartY.value
}

// 停止拖动
const stopDrag = () => {
  isDragging.value = false
  draggingIndex.value = -1
  document.removeEventListener('mousemove', onDrag)
  document.removeEventListener('mouseup', stopDrag)
}

// 放大
const zoomIn = () => {
  if (selectedItemIndex.value === -1) return
  const index = selectedItemIndex.value
  clothesTransform[index].scale = Math.min(clothesTransform[index].scale + 0.1, 3)
}

// 缩小
const zoomOut = () => {
  if (selectedItemIndex.value === -1) return
  const index = selectedItemIndex.value
  clothesTransform[index].scale = Math.max(clothesTransform[index].scale - 0.1, 0.5)
}

// 左旋转
const rotateLeft = () => {
  if (selectedItemIndex.value === -1) return
  const index = selectedItemIndex.value
  clothesTransform[index].rotate -= 15
}

// 右旋转
const rotateRight = () => {
  if (selectedItemIndex.value === -1) return
  const index = selectedItemIndex.value
  clothesTransform[index].rotate += 15
}

// 重置变换
const resetTransform = () => {
  if (selectedItemIndex.value === -1) return
  const index = selectedItemIndex.value
  clothesTransform[index] = {
    x: 0,
    y: 0,
    scale: 1,
    rotate: 0,
    zIndex: index
  }
}

// 保存预览图片
const savePreview = async () => {
  if (!previewCanvas.value) return
  try {
    // 等待所有图片加载完成
    const images = previewCanvas.value.getElementsByTagName('img')
    await Promise.all(Array.from(images).map(img => {
      if (img.complete) return Promise.resolve()
      return new Promise((resolve, reject) => {
        img.onload = resolve
        img.onerror = reject
      })
    }))

    const canvas = await html2canvas(previewCanvas.value, {
      useCORS: true,
      allowTaint: true,
      backgroundColor: '#ffffff',
      scale: 2,
      logging: false,
      onclone: (clonedDoc) => {
        const clonedItems = clonedDoc.getElementsByClassName('preview-item') as HTMLCollectionOf<HTMLElement>
        Array.from(clonedItems).forEach((item, index) => {
          const transform = clothesTransform[index] || { x: 0, y: 0, scale: 1, rotate: 0, zIndex: 0 }
          item.style.transform = `translate(calc(-50% + ${transform.x}px), calc(-50% + ${transform.y}px)) scale(${transform.scale}) rotate(${transform.rotate}deg)`
          const img = item.querySelector('img')
          if (img) {
            img.crossOrigin = 'anonymous'
            img.style.width = '60px'
            img.style.height = '60px'
            img.style.objectFit = 'contain'
          }
        })
      }
    })

    const link = document.createElement('a')
    link.download = '穿搭预览.png'
    link.href = canvas.toDataURL('image/png', 1.0)
    link.click()
    ElMessage.success('图片保存成功')
  } catch (error) {
    console.error('保存图片失败:', error)
    ElMessage.error('保存图片失败')
  }
}

// 打开预览
const openPreview = () => {
  initClothesTransform()
  showPreviewDialog.value = true
}

// 获取标签类型
const getTagType = (category: string) => {
  const types: Record<string, string> = {
    '上衣': 'primary',
    '下装': 'success',
    '鞋子': 'warning',
    '配饰': 'info'
  }
  return types[category] || 'default'
}

// 添加过滤后的穿搭列表
const filteredOutfitList = computed(() => {
  if (!searchKeyword.value) return outfitList.value
  
  const keyword = searchKeyword.value.toLowerCase()
  return outfitList.value.filter(outfit => 
    outfit.name.toLowerCase().includes(keyword) ||
    (outfit.description && outfit.description.toLowerCase().includes(keyword))
  )
})

// 监听路由变化
watch(() => route.path, (newPath) => {
  if (newPath === '/favorite') {
    initData()
  }
})

// 组件挂载时获取数据
onMounted(() => {
  initData()
})

// 处理对话框关闭
const handleCloseDialog = () => {
  showCreateDialog.value = false
}
</script>

<style scoped>
.favorite-container {
  padding: 20px;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 20px;
}

.search-input {
  width: 200px;
  transition: all 0.3s ease;
  margin-left: 24px;

  :deep(.el-input__wrapper) {
    background-color: #f5f7fa;
    box-shadow: none !important;
    border-radius: 4px;
    padding: 4px 12px;
    height: 40px;
    border: 1px solid #e4e7ed;
    transition: all 0.3s ease;
  }

  :deep(.el-input__inner) {
    font-size: 14px;
    color: #606266;
    height: 40px;
    line-height: 40px;
    background: transparent;

    &::placeholder {
      color: #909399;
    }
  }

  :deep(.el-input__prefix) {
    font-size: 16px;
    color: #909399;
    margin-right: 8px;
  }

  :deep(.el-input__suffix) {
    color: #909399;
  }

  &:hover {
    :deep(.el-input__wrapper) {
      border-color: #c0c4cc;
    }
  }

  &:focus-within {
    :deep(.el-input__wrapper) {
      border-color: #2d5a9d;
      box-shadow: 0 0 0 1px #2d5a9d inset;
    }

    :deep(.el-input__prefix) {
      color: #2d5a9d;
    }
  }
}

.outfit-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 20px;
}

.outfit-card {
  border-radius: 12px;
  overflow: hidden;
  transition: all 0.3s;
}

.outfit-card:hover {
  transform: translateY(-5px);
  box-shadow: 0 5px 15px rgba(0, 0, 0, 0.1);
}

.image-wrapper {
  position: relative;
  height: 300px;
  overflow: hidden;
}

.outfit-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
  transition: transform 0.3s;
}

.outfit-card:hover .outfit-image {
  transform: scale(1.05);
}

.image-overlay {
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

.outfit-card:hover .image-overlay {
  opacity: 1;
}

.action-button {
  margin: 0 5px;
}

.outfit-info {
  padding: 15px;
}

.outfit-info h3 {
  margin: 0 0 10px;
  font-size: 16px;
  color: #303133;
}

.description {
  color: #606266;
  font-size: 14px;
  margin-bottom: 10px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.clothes-list {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.clothes-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 5px;
  background: #f5f7fa;
  border-radius: 4px;
}

.clothes-thumbnail {
  width: 40px;
  height: 40px;
  border-radius: 4px;
}

.clothes-name {
  font-size: 12px;
  color: #606266;
}

.outfit-form {
  :deep(.el-form-item) {
    margin-bottom: 16px;
  }

  :deep(.el-form-item__label) {
    padding-bottom: 4px;
  }

  :deep(.el-form-item__content) {
    line-height: 1;
  }
}

.image-upload-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  width: 100%;
}

.form-actions {
  display: flex;
  flex-direction: column;
  gap: 16px;
  width: 100%;
  margin-top: 8px;
}

.select-clothes-btn {
  width: 100%;
  height: 40px;
  font-size: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.action-buttons {
  display: flex;
  gap: 12px;
  width: 100%;
  justify-content: center;
}

.avatar-uploader {
  width: 100%;
}

.upload-area {
  width: 200px;
  height: 200px;
  margin: 0 auto;
  border: 2px dashed #dcdfe6;
  border-radius: 12px;
  overflow: hidden;
  transition: all 0.3s;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}

.upload-area:hover {
  border-color: #2d5a9d;
  background: rgba(45, 90, 157, 0.1);
}

.avatar {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.upload-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #909399;
  padding: 20px;
  gap: 12px;
}

.upload-icon {
  font-size: 48px;
  color: #c0c4cc;
}

.upload-text {
  font-size: 14px;
  color: #909399;
  margin-top: 8px;
}

.el-progress {
  margin-bottom: 8px;
}

.image-tips {
  text-align: center;
  margin-top: 8px;
  color: #909399;
  font-size: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
}

.selected-clothes {
  max-height: 300px;
  overflow-y: auto;
  background: #f5f7fa;
  border-radius: 8px;
  padding: 12px;
}

.selected-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  background: #fff;
  border-radius: 8px;
  margin-bottom: 8px;
  transition: all 0.3s;
}

.selected-item:last-child {
  margin-bottom: 0;
}

.selected-item:hover {
  transform: translateY(-2px);
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
}

.selected-image {
  width: 48px;
  height: 48px;
  border-radius: 6px;
  object-fit: cover;
}

.item-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.item-name {
  font-size: 14px;
  color: #303133;
  font-weight: 500;
}

.preview-dialog {
  :deep(.el-dialog__body) {
    padding: 0;
    height: 100vh;
  }

  :deep(.el-dialog__header) {
    padding: 0;
    margin: 0;
  }

  :deep(.el-dialog__headerbtn) {
    z-index: 100;
  }
}

.preview-container {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: #f5f7fa;
}

.preview-toolbar {
  padding: 16px 24px;
  background: #fff;
  border-bottom: 1px solid #dcdfe6;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.toolbar-left,
.toolbar-right {
  display: flex;
  gap: 12px;
  align-items: center;
}

.preview-main {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
}

.preview-canvas {
  width: 800px;
  height: 800px;
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
  position: relative;
}

.preview-item {
  user-select: none;
  will-change: transform;
  width: 80px;
  height: 80px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border-radius: 4px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
  cursor: move;
  position: absolute;
  top: 50%;
  left: 50%;
  transform-origin: center center;
}

.preview-item.selected {
  box-shadow: 0 0 0 2px #2d5a9d;
  z-index: 10;
}

.preview-image {
  width: 60px;
  height: 60px;
  pointer-events: none;
  object-fit: contain;
  display: block;
}

.create-dialog {
  :deep(.el-dialog__body) {
    padding: 30px;
  }

  :deep(.el-dialog__header) {
    padding: 20px;
    border-bottom: 1px solid #dcdfe6;
    margin: 0;
  }
}

.dialog-content {
  display: flex;
  flex-direction: column;
}

.outfit-form {
  width: 100%;
  max-width: 600px;
  margin: 0 auto;
}

.clothes-form-item {
  margin-bottom: 0 !important;
}

.clothes-container {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.selected-clothes {
  max-height: 300px;
  overflow-y: auto;
  background: #f5f7fa;
  border-radius: 8px;
  padding: 12px;
}

.clothes-actions {
  display: flex;
  gap: 12px;
  justify-content: center;
}

.select-clothes-btn,
.preview-btn {
  flex: 1;
  max-width: 200px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.form-footer {
  margin-top: 24px;
  padding-top: 24px;
  border-top: 1px solid #dcdfe6;
  display: flex;
  justify-content: center;
  gap: 12px;
}

.clothes-selector {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.clothes-search-input {
  margin-bottom: 16px;

  :deep(.el-input__wrapper) {
    background-color: #f5f7fa;
    box-shadow: none !important;
    border: 1px solid #e4e7ed;
    border-radius: 4px;
    padding: 4px 12px;
    height: 40px;
    transition: all 0.3s ease;
  }

  :deep(.el-input__inner) {
    font-size: 14px;
    color: #606266;
    height: 40px;
    line-height: 40px;
    background: transparent;

    &::placeholder {
      color: #909399;
    }
  }

  :deep(.el-input__prefix) {
    font-size: 16px;
    color: #909399;
    margin-right: 8px;
  }

  &:hover {
    :deep(.el-input__wrapper) {
      border-color: #c0c4cc;
    }
  }

  &:focus-within {
    :deep(.el-input__wrapper) {
      border-color: #2d5a9d;
      box-shadow: 0 0 0 1px #2d5a9d inset;
    }

    :deep(.el-input__prefix) {
      color: #2d5a9d;
    }
  }
}

.clothes-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(100px, 1fr));
  gap: 12px;
  max-height: 400px;
  overflow-y: auto;
  padding: 8px;
}

.clothes-selector-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 8px;
  background: #f5f7fa;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.3s;
}

.clothes-selector-item:hover {
  background: rgba(45, 90, 157, 0.1);
  transform: translateY(-2px);
}

.clothes-selector-item.selected {
  background: rgba(45, 90, 157, 0.1);
  border: 1px solid #2d5a9d;
}

.selector-image {
  width: 60px;
  height: 60px;
  border-radius: 4px;
  object-fit: cover;
}

.selector-info {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  width: 100%;
}

.selector-info span {
  font-size: 12px;
  color: #303133;
  text-align: center;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  width: 100%;
}

:deep(.el-button--primary) {
  background-color: #2d5a9d;
  border-color: #2d5a9d;
}

:deep(.el-button--primary:hover) {
  background-color: #3468b5;
  border-color: #3468b5;
}

:deep(.el-select .el-input__wrapper) {
  box-shadow: 0 0 0 1px #dcdfe6 inset;
}

:deep(.el-select:hover .el-input__wrapper) {
  box-shadow: 0 0 0 1px #2d5a9d inset;
}

:deep(.el-select .el-input__wrapper.is-focus) {
  box-shadow: 0 0 0 1px #2d5a9d inset;
}
</style> 
