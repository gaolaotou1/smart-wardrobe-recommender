<template>
  <div class="wardrobe-container">
    <!-- 顶部统计卡片 -->
    <el-row :gutter="20" class="statistics" justify="center">
      <el-col :span="8" v-for="stat in statistics" :key="stat.title">
        <el-card class="stat-card" shadow="hover">
          <div class="stat-icon">
            <el-icon><component :is="stat.icon" /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-title">{{ stat.title }}</div>
            <div class="stat-number">{{ stat.number }}</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 筛选和操作栏 -->
    <div class="operation-bar">
      <div class="left">
        <el-button type="primary" @click="handleAdd" class="add-button">
          <el-icon><Plus /></el-icon>添加衣物
        </el-button>
      </div>
      <div class="right">
        <el-input
          v-model="filters.keyword"
          placeholder="搜索衣物"
          class="search-input"
          clearable
          @clear="handleFilterChange"
          @input="handleFilterChange"
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
        <el-select 
          v-model="filters.category" 
          placeholder="选择分类" 
          clearable
          class="filter-select"
          @change="handleFilterChange"
        >
          <el-option
            v-for="item in categoryOptions"
            :key="item.value"
            :label="item.label"
            :value="item.value"
          />
        </el-select>
        <el-select 
          v-model="filters.season" 
          placeholder="选择季节" 
          clearable
          class="filter-select"
          @change="handleFilterChange"
        >
          <el-option
            v-for="item in seasonOptions"
            :key="item.value"
            :label="item.label"
            :value="item.value"
          />
        </el-select>
        <el-select 
          v-model="filters.occasion" 
          placeholder="选择场合" 
          clearable
          class="filter-select"
          @change="handleFilterChange"
        >
          <el-option
            v-for="item in occasionOptions"
            :key="item.value"
            :label="item.label"
            :value="item.value"
          />
        </el-select>
      </div>
    </div>

    <!-- 衣物展示区 -->
    <div class="clothes-grid">
      <el-card
        v-for="item in clothesList"
        :key="item.id"
        class="clothes-card"
        shadow="hover"
      >
        <div class="card-content">
          <div class="image-wrapper">
            <el-image
              :src="item.image_url"
              fit="contain"
              :preview-src-list="[item.image_url]"
              class="clothes-image"
            >
              <template #error>
                <div class="image-placeholder">
                  <el-icon><Picture /></el-icon>
                </div>
              </template>
            </el-image>
            <div class="image-overlay">
              <el-button-group>
                <el-button type="primary" @click="handleEdit(item)" class="action-button">
                  <el-icon><Edit /></el-icon>
                </el-button>
                <el-button type="danger" @click="handleDelete(item.id)" class="action-button">
                  <el-icon><Delete /></el-icon>
                </el-button>
              </el-button-group>
            </div>
          </div>
          <div class="clothes-info">
            <h3>{{ item.name }}</h3>
            <div class="tags">
              <el-tag size="small" type="info">{{ item.category }}</el-tag>
              <el-tag size="small" type="success">{{ getSeasonName(item.season) }}</el-tag>
              <div class="occasion-tags">
                <el-tag 
                  v-for="occasion in item.occasions" 
                  :key="occasion"
                  size="small"
                  type="warning"
                >
                  {{ occasion }}
                </el-tag>
              </div>
            </div>
            <div class="details">
              <div class="detail-row">
                <p v-if="item.brand"><span>品牌：</span>{{ item.brand }}</p>
                <p><span>风格：</span>{{ item.style }}</p>
              </div>
              <div class="detail-row">
                <p><span>材质：</span>{{ item.material }}</p>
                <p><span>厚度：</span>{{ item.thickness }}</p>
              </div>
            </div>
          </div>
        </div>
      </el-card>
    </div>

    <!-- 添加/编辑衣物对话框 -->
    <el-dialog
      :title="dialogType === 'add' ? '添加衣物' : '编辑衣物'"
      v-model="showAddDialog"
      width="800px"
      :close-on-click-modal="false"
      @close="handleDialogClose"
    >
      <div class="dialog-content">
        <!-- 左侧步骤指示器 -->
        <div class="steps-sidebar">
          <div 
            v-for="(step, index) in steps" 
            :key="step.title"
            class="step-item"
            :class="{ 
              'active': activeStep === index,
              'completed': activeStep > index 
            }"
            @click="handleStepClick(index)"
          >
            <div class="step-icon">
              <el-icon v-if="activeStep > index"><Check /></el-icon>
              <span v-else>{{ index + 1 }}</span>
            </div>
            <div class="step-info">
              <div class="step-title">{{ step.title }}</div>
              <div class="step-desc">{{ step.desc }}</div>
            </div>
          </div>
        </div>

        <!-- 右侧表单内容 -->
        <div class="form-content">
          <!-- 步骤1：图片上传 -->
          <div v-if="activeStep === 0" class="step-form">
            <div class="upload-container">
              <!-- 预览区域 -->
              <div class="preview-area" v-if="clothesForm.image_url">
                <el-image
                  :src="clothesForm.image_url"
                  class="preview-image"
                  fit="contain"
                  :preview-src-list="[clothesForm.image_url]"
                />
                <div class="preview-actions">
                  <el-button type="danger" @click="removeImage">
                    <el-icon><Delete /></el-icon>删除图片
                  </el-button>
                </div>
              </div>

              <!-- 上传区域 -->
              <el-upload
                v-else
                class="upload-area"
                :action="uploadUrl"
                :auto-upload="true"
                :show-file-list="false"
                :before-upload="beforeUpload"
                :on-success="handleUploadSuccess"
                :on-error="handleUploadError"
                :headers="uploadHeaders"
                drag
                accept=".jpg,.jpeg,.png"
              >
                <div class="upload-content" v-if="!isProcessing">
                  <el-icon class="upload-icon"><Upload /></el-icon>
                  <div class="upload-text">
                    <h3>点击或拖拽图片到此处上传</h3>
                    <p>支持 jpg、jpeg、png 格式</p>
                  </div>
                </div>
                <div v-else class="processing-mask">
                  <el-icon class="processing-icon"><Loading /></el-icon>
                  <p>正在处理图片，请稍候...</p>
                </div>
              </el-upload>

              <!-- 上传提示 -->
              <div class="upload-tips">
                <div class="tip-item">
                  <el-icon><InfoFilled /></el-icon>
                  <span>支持 jpg、png 格式图片</span>
                </div>
                <div class="tip-item">
                  <el-icon><Warning /></el-icon>
                  <span>图片大小不超过 5MB</span>
                </div>
              </div>
            </div>
          </div>

          <!-- 步骤2：基本信息 -->
          <div v-if="activeStep === 1" class="step-form">
            <!-- AI 分析结果展示 -->
            <div v-if="aiAnalysis" class="ai-analysis">
              <el-alert
                title="AI 分析结果"
                type="info"
                :closable="false"
                show-icon
              >
                <template #default>
                  <div class="analysis-details">
                    <p>分类：{{ aiAnalysis.category }}</p>
                    <p>风格：{{ aiAnalysis.style }}</p>
                    <p>颜色：{{ aiAnalysis.color }}</p>
                    <p>季节：{{ aiAnalysis.season }}</p>
                    <p>材质：{{ aiAnalysis.material }}</p>
                    <p>场合：{{ aiAnalysis.occasions.join('、') }}</p>
                    <p>描述：{{ aiAnalysis.description }}</p>
                    <p>厚度：{{ aiAnalysis.thickness }}</p>
                  </div>
                </template>
              </el-alert>
            </div>

            <el-form
              ref="formRef"
              :model="clothesForm"
              :rules="rules"
              label-width="100px"
              class="clothes-form"
            >
              <el-form-item label="衣物名称" prop="name">
                <el-input v-model="clothesForm.name" placeholder="请输入衣物名称" />
              </el-form-item>
              <el-form-item label="衣物分类" prop="category">
                <el-select
                  v-model="clothesForm.category"
                  placeholder="请选择衣物分类"
                  style="width: 100%"
                >
                  <el-option
                    v-for="item in categoryOptions"
                    :key="item.value"
                    :label="item.label"
                    :value="item.value"
                  />
                </el-select>
              </el-form-item>
              <el-form-item 
                v-if="clothesForm.category"
                label="具体分类" 
                prop="subCategory"
              >
                <el-select
                  v-model="clothesForm.subCategory"
                  placeholder="请选择具体分类"
                  style="width: 100%"
                >
                  <el-option
                    v-for="item in currentSubCategoryOptions"
                    :key="item.value"
                    :label="item.label"
                    :value="item.value"
                  />
                </el-select>
              </el-form-item>
              <el-form-item label="风格" prop="style">
                <el-select
                  v-model="clothesForm.style"
                  placeholder="请选择风格"
                  style="width: 100%"
                >
                  <el-option
                    v-for="item in styleOptions"
                    :key="item.value"
                    :label="item.label"
                    :value="item.value"
                  />
                </el-select>
              </el-form-item>
              <el-form-item label="场合" prop="occasions">
                <el-select
                  v-model="clothesForm.occasions"
                  multiple
                  placeholder="请选择场合"
                  style="width: 100%"
                >
                  <el-option
                    v-for="item in occasionOptions"
                    :key="item.value"
                    :label="item.label"
                    :value="item.value"
                  />
                </el-select>
              </el-form-item>
              <el-form-item label="材质" prop="material">
                <el-select
                  v-model="clothesForm.material"
                  placeholder="请选择材质"
                  style="width: 100%"
                >
                  <el-option
                    v-for="item in materialOptions"
                    :key="item.value"
                    :label="item.label"
                    :value="item.value"
                  />
                </el-select>
              </el-form-item>
              <el-form-item label="厚度" prop="thickness">
                <el-select
                  v-model="clothesForm.thickness"
                  placeholder="请选择厚度"
                  style="width: 100%"
                >
                  <el-option
                    v-for="item in thicknessOptions"
                    :key="item.value"
                    :label="item.label"
                    :value="item.value"
                  />
                </el-select>
              </el-form-item>
              <el-form-item label="季节" prop="season">
                <el-select
                  v-model="clothesForm.season"
                  placeholder="请选择季节"
                  style="width: 100%"
                >
                  <el-option
                    v-for="item in seasonOptions"
                    :key="item.value"
                    :label="item.label"
                    :value="item.value"
                  />
                </el-select>
              </el-form-item>
            </el-form>
          </div>

          <!-- 步骤3：颜色信息 -->
          <div v-if="activeStep === 2" class="step-form">
            <el-form
              ref="formRef"
              :model="clothesForm"
              :rules="rules"
              label-width="100px"
              class="clothes-form"
            >
              <el-form-item label="颜色系" prop="color">
                <el-select v-model="clothesForm.color" placeholder="请选择颜色系" style="width: 100%">
                  <el-option v-for="item in colorOptions" :key="item.value" :label="item.label" :value="item.value" />
                </el-select>
              </el-form-item>
              <el-form-item label="具体颜色" prop="subColor" v-if="clothesForm.color">
                <el-select v-model="clothesForm.subColor" placeholder="请选择具体颜色" style="width: 100%">
                  <el-option v-for="item in currentSubColorOptions" :key="item.value" :label="item.label" :value="item.value" />
                </el-select>
              </el-form-item>
            </el-form>
          </div>

          <!-- 步骤4：描述信息 -->
          <div v-if="activeStep === 3" class="step-form">
            <el-form
              ref="formRef"
              :model="clothesForm"
              :rules="rules"
              label-width="100px"
              class="clothes-form"
            >
              <el-form-item label="描述" prop="description">
                <el-input
                  v-model="clothesForm.description"
                  type="textarea"
                  :rows="4"
                  placeholder="请输入衣物描述"
                />
              </el-form-item>
            </el-form>
          </div>
        </div>
      </div>

      <template #footer>
        <div class="dialog-footer">
          <div class="left">
            <el-button @click="handleCancel" plain>取消</el-button>
          </div>
          <div class="right">
            <el-button 
              v-if="activeStep > 0" 
              @click="activeStep--"
              plain
            >
              上一步
            </el-button>
            <el-button 
              type="primary" 
              v-if="activeStep < steps.length - 1" 
              @click="handleNextStep"
            >
              下一步
            </el-button>
            <el-button 
              type="primary" 
              v-else 
              @click="handleSubmit"
            >
              完成
            </el-button>
          </div>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, onUnmounted, watch, computed, nextTick } from 'vue'
import type { FormInstance } from 'element-plus'
import { ElMessage, ElMessageBox } from 'element-plus'
import axios from 'axios'
import { debounce } from 'lodash-es'
import {
  Plus,
  Search,
  Picture,
  Edit,
  Delete,
  Check,
  Upload,
  InfoFilled,
  Warning,
  Goods,
  Calendar,
  Star,
  Collection
} from '@element-plus/icons-vue'
import type { Filters, Category, OccasionTag, ClothesItem, ClothesForm, AIAnalysis, Step } from '@/types'
import { useRouter } from 'vue-router'

// 添加axios基础URL配置
axios.defaults.baseURL = import.meta.env.VITE_API_BASE_URL || ''

const showAddDialog = ref(false)
const dialogType = ref('add')
const filters = reactive<Filters>({
  keyword: '',
  category: '',
  season: '',
  occasion: ''
})

const clothesForm = reactive<ClothesForm>({
  id: '',
  name: '',
  category: '',
  subCategory: '',
  brand: '',
  color: '',
  colorName: '',
  season: '',
  occasions: [],
  style: '',
  material: '',
  image_url: '',
  description: '',
  thickness: '',
  hash: ''
})

const clothesList = ref<ClothesItem[]>([])
const categories = ref<Category[]>([])

const statistics = reactive([
  {
    title: '衣物总数',
    number: 0,
    icon: Goods
  },
  {
    title: '本季衣物',
    number: 0,
    icon: Calendar
  },
  {
    title: '穿搭总数',
    number: 0,
    icon: Collection
  }
])

const activeStep = ref<number>(0)

// 步骤定义
const steps: Step[] = [
  { title: '上传图片', desc: '上传衣物照片' },
  { title: '基本信息', desc: '填写衣物信息' },
  { title: '颜色信息', desc: '选择颜色' },
  { title: '描述信息', desc: '添加描述' }
]

// 上传相关配置
const uploadUrl = `${axios.defaults.baseURL}/api/upload`
const uploadFiles = ref<{ raw: File }[]>([])
const isProcessing = ref(false)
const uploadHeaders = {
  Authorization: localStorage.getItem('token') || '',
  'X-User-ID': localStorage.getItem('userId') || ''  // 添加用户ID到请求头
}

// 添加 AI 分析结果状态
const aiAnalysis = ref<AIAnalysis | null>(null)

// 表单验证规则
const rules = {
  name: [{ required: true, message: '请输入衣物名称', trigger: 'blur' }],
  category: [{ required: true, message: '请选择衣物分类', trigger: 'change' }],
  subCategory: [{ required: true, message: '请选择具体分类', trigger: 'change' }],
  color: [{ required: true, message: '请选择颜色', trigger: 'change' }],
  season: [{ required: true, message: '请选择季节', trigger: 'change' }],
  style: [{ required: true, message: '请选择风格', trigger: 'change' }],
  material: [{ required: true, message: '请选择材质', trigger: 'change' }],
  thickness: [{ required: true, message: '请选择厚度', trigger: 'change' }],
  description: [{ required: true, message: '请输入描述', trigger: 'blur' }]
}

// 添加表单引用
const formRef = ref<FormInstance>()

// 添加新的数据
const predefineColors = [
  '#ff4500', '#ff8c00', '#ffd700',
  '#90ee90', '#00ced1', '#1e90ff',
  '#c71585', '#000000', '#ffffff'
]

// 修改分类选项的定义
const categoryOptions = [
  { label: '上装', value: '上装' },
  { label: '下装', value: '下装' },
  { label: '套装', value: '套装' }
]

// 修改子分类选项
const subCategoryOptions = {
  '上装': [
    { label: 'T恤衫', value: 'T恤衫' },
    { label: '衬衫', value: '衬衫' },
    { label: '吊带', value: '吊带' },
    { label: '西装', value: '西装' },
    { label: '卫衣', value: '卫衣' },
    { label: '毛衣', value: '毛衣' },
    { label: '外套', value: '外套' },
    { label: '羽绒服', value: '羽绒服' }
  ],
  '下装': [
    { label: '背带裙', value: '背带裙' },
    { label: '直筒裙', value: '直筒裙' },
    { label: 'A型裙', value: 'A型裙' },
    { label: '百褶裙', value: '百褶裙' },
    { label: '包臀裙', value: '包臀裙' },
    { label: '蓬蓬裙', value: '蓬蓬裙' },
    { label: '纱裙', value: '纱裙' },
    { label: '短裤', value: '短裤' },
    { label: '西装裤', value: '西装裤' },
    { label: '牛仔裤', value: '牛仔裤' },
    { label: '休闲裤', value: '休闲裤' },
    { label: '运动裤', value: '运动裤' },
    { label: '阔腿裤', value: '阔腿裤' },
    { label: '工装裤', value: '工装裤' }
  ],
  '套装': [
    { label: '连衣裙', value: '连衣裙' },
    { label: '连体衣', value: '连体衣' },
    { label: '西装套装', value: '西装套装' },
    { label: '运动套装', value: '运动套装' },
    { label: '唐装', value: '唐装' },
    { label: '汉服', value: '汉服' }
  ]
}

// 修改计算属性，获取当前主分类对应的子分类选项
const currentSubCategoryOptions = computed(() => {
  return subCategoryOptions[clothesForm.category] || []
})

// 修改主分类变化的监听器
watch(() => clothesForm.category, () => {
  clothesForm.subCategory = ''
})

// 修改筛选变化处理函数，添加防抖
const handleFilterChange = debounce(() => {
  console.log('筛选条件变化:', filters)
  getClosthesList()
}, 300)

// 修改获取衣物列表函数
const getClosthesList = async () => {
  try {
    console.log('发送请求，参数:', filters)
    const userId = localStorage.getItem('userId')
    if (!userId) {
      ElMessage.warning('请先登录')
      router.push('/login')
      return
    }
    const res = await axios.get('/api/clothes', { 
      params: {
        ...filters,
        user_id: userId  // 添加用户ID参数
      }
    })
    console.log('收到响应:', res.data)
    if (res.data.code === 200) {
      clothesList.value = res.data.data
      // 获取统计数据
      getStatistics()
    } else {
      ElMessage.error(res.data.message || '获取衣物列表失败')
    }
  } catch (error) {
    console.error('获取衣物列表失败:', error)
    ElMessage.error('获取衣物列表失败')
  }
}

// 修改获取统计数据的函数
const getStatistics = async () => {
  try {
    const userId = localStorage.getItem('userId')
    if (!userId) {
      return
    }
    const res = await axios.get('/api/clothes/statistics', {
      params: {
        user_id: userId  // 添加用户ID参数
      }
    })
    if (res.data.code === 200) {
      const data = res.data.data
      statistics[0].number = data.total
      statistics[1].number = data.season
      statistics[2].number = data.outfit
    } else {
      ElMessage.error(res.data.message || '获取统计数据失败')
    }
  } catch (error) {
    console.error('获取统计数据失败:', error)
    ElMessage.error('获取统计数据失败')
  }
}

// 处理编辑
const handleEdit = async (item: ClothesItem) => {
  dialogType.value = 'edit'
  // 先赋主分类和颜色系
  clothesForm.category = item.category || ''
  clothesForm.color = item.color || ''
  await nextTick()
  // 再赋子分类和具体颜色
  clothesForm.subCategory = item.subCategory || item.sub_category || ''
  clothesForm.subColor = item.subColor || item.sub_color || ''
  clothesForm.id = item.id || ''
  clothesForm.name = item.name || ''
  clothesForm.brand = item.brand || ''
  clothesForm.season = item.season || ''
  clothesForm.occasions = item.occasions || []
  clothesForm.style = item.style || ''
  clothesForm.material = item.material || ''
  clothesForm.image_url = item.image_url || ''
  clothesForm.description = item.description || ''
  clothesForm.thickness = item.thickness || ''
  showAddDialog.value = true
}

// 处理删除
const handleDelete = async (id: number) => {
  try {
    const confirmResult = await ElMessageBox.confirm('确定要删除这件衣物吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })

    if (confirmResult === 'confirm') {
      const response = await axios.delete(`/api/clothes/${id}`)
      if (response.data.code === 200) {
        ElMessage.success('删除成功')
        getClosthesList()
      } else {
        throw new Error(response.data.message || '删除失败')
      }
    }
  } catch (error: any) {
    console.error('删除衣物失败:', error)
    ElMessage.error(error.message || '删除失败，请重试')
  }
}

// 修改 handleSubmit 函数
const handleSubmit = async () => {
  try {
    const submitData = {
      ...clothesForm,
      user_id: localStorage.getItem('userId') || ''
    }
    
    console.log('提交数据:', submitData)
    
    let response;
    if (dialogType.value === 'edit') {
      // 编辑操作使用 PUT 请求
      response = await axios.put(`/api/clothes/${clothesForm.id}`, submitData)
    } else {
      // 新建操作使用 POST 请求
      response = await axios.post('/api/clothes', submitData)
    }

    if (response.data.code === 200) {
      ElMessage.success(dialogType.value === 'edit' ? '更新成功' : '添加成功')
      showAddDialog.value = false
      getClosthesList()
    } else {
      ElMessage.error(response.data.message || (dialogType.value === 'edit' ? '更新失败' : '添加失败'))
    }
  } catch (error) {
    console.error(dialogType.value === 'edit' ? '更新衣物失败:' : '添加衣物失败:', error)
    ElMessage.error(dialogType.value === 'edit' ? '更新失败，请重试' : '添加失败，请重试')
  }
}

// 添加上传文件的类型定义
interface UploadFile {
  raw: File
}

// 上传前验证
const beforeUpload = (file: File) => {
  const isImage = file.type.startsWith('image/')
  const isLt5M = file.size / 1024 / 1024 < 5

  if (!isImage) {
    ElMessage.error('只能上传图片文件!')
    return false
  }
  if (!isLt5M) {
    ElMessage.error('图片大小不能超过 5MB!')
    return false
  }
  
  // 检查用户是否已登录
  const userId = localStorage.getItem('userId')
  if (!userId) {
    ElMessage.error('请先登录')
    return false
  }
  
  // 保存文件引用
  uploadFiles.value = [{ raw: file }]
  isProcessing.value = true
  return true
}

// 上传成功处理
const handleUploadSuccess = async (response: any) => {
  console.log('Upload response:', response)
  
  // 重置处理状态
  isProcessing.value = false
  uploadFiles.value = []
  
  // 处理非衣物图片或相似图片的情况
  if (response.code === 400) {
    if ('is_clothes' in response) {
      // 统一处理相似图片和非衣物图片的情况
      const message = response.is_duplicate 
        ? '检测到相似图片，该衣物可能已经上传过。是否继续添加？'
        : '检测到非衣物图片，是否继续添加？'
      
      const confirmResult = await ElMessageBox.confirm(
        message,
        '提示',
        {
          confirmButtonText: '继续添加',
          cancelButtonText: '取消',
          type: 'warning'
        }
      )
      
      if (confirmResult === 'confirm') {
        // 设置图片URL
        clothesForm.image_url = response.bed_url || `${axios.defaults.baseURL}${response.url}`
        clothesForm.hash = response.hash
        // 显示图片
        activeStep.value = 1
        // 显示成功消息
        ElMessage.success('图片上传成功，请继续填写衣物信息')
      } else {
        // 如果用户取消，清空图片
        clothesForm.image_url = ''
        clothesForm.hash = ''
      }
    } else {
      ElMessage.error(response.message || '上传失败')
    }
    return
  }
  
  if (response.code === 200) {
    clothesForm.image_url = response.bed_url || `${axios.defaults.baseURL}${response.url}`
    clothesForm.hash = response.hash
    
    if (response.ai_analysis) {
      aiAnalysis.value = response.ai_analysis
      clothesForm.name = response.ai_analysis.description || ''
      clothesForm.category = response.ai_analysis.category || ''
      clothesForm.style = response.ai_analysis.style || ''
      clothesForm.color = response.ai_analysis.color || ''
      clothesForm.colorName = response.ai_analysis.color || ''
      clothesForm.season = response.ai_analysis.season || ''
      clothesForm.material = response.ai_analysis.material || ''
      clothesForm.description = response.ai_analysis.description || ''
      clothesForm.thickness=response.ai_analysis.thickness || ''
      // 处理场合标签
      if (response.ai_analysis.occasions && Array.isArray(response.ai_analysis.occasions)) {
        clothesForm.occasions = response.ai_analysis.occasions
      }
      
      ElMessage.success('AI 分析完成，您可以修改以下信息')
    }
    
    activeStep.value = 1
  } else {
    ElMessage.error(response.message || '上传失败')
  }
}

// 上传错误处理
const handleUploadError = (error: any) => {
  console.error('Upload error:', error)
  isProcessing.value = false
  uploadFiles.value = []
  ElMessage.error('上传失败，请重试')
}

const getSeasonType = (season: string): string => {
  const types: Record<string, string> = {
    'spring_and_autumn': 'success',
    'summer': 'warning',
    'winter': 'danger',
    'all_season': 'info'
  }
  return types[season] || 'info'
}

const styleOptions = [
  { label: '休闲', value: '休闲' },
  { label: '正式', value: '正式' },
  { label: '潮流', value: '潮流' },
  { label: '复古', value: '复古' },
  { label: '优雅', value: '优雅' },
  { label: '甜美', value: '甜美' },
  { label: '国风', value: '国风' },
  { label: '日韩', value: '日韩' },
  { label: '其他', value: '其他' }
]

const materialOptions = [
  { label: '棉质', value: '棉质' },
  { label: '丝绸', value: '丝绸' },
  { label: '羊毛', value: '羊毛' },
  { label: '尼龙', value: '尼龙' },
  { label: '涤纶', value: '涤纶' },
  { label: '皮革', value: '皮革' },
  { label: '牛仔', value: '牛仔' },
  { label: '麻料', value: '麻料' },
  { label: '其他', value: '其他' }
]

const seasonOptions = [
  { label: '春秋季', value: 'spring_and_autumn' },
  { label: '夏季', value: 'summer' },
  { label: '冬季', value: 'winter' },
  { label: '四季通用', value: 'all_season' }
]

// 修改场合标签的定义
const occasionOptions = [
  { label: '旅行度假场合', value: '旅行度假场合' },
  { label: '都市休闲场合', value: '都市休闲场合' },
  { label: '户外运动场合', value: '户外运动场合' },
  { label: '日常社交场合', value: '日常社交场合' },
  { label: '商务交流场合', value: '商务交流场合' },
  { label: '正式职业场合', value: '正式职业场合' },
]

// 添加厚度选项
const thicknessOptions = [
  { label: '常规', value: '常规' },
  { label: '薄款', value: '薄款' },
  { label: '厚款', value: '厚款' },
  { label: '加绒', value: '加绒' },
  { label: '加厚', value: '加厚' }
]

// 修改下一步处理函数
const handleNextStep = async () => {
  if (activeStep.value === 0 && !clothesForm.image_url) {
    ElMessage.warning('请先上传图片')
    return
  }

  // 如果是第一步，直接进入下一步（因为已经上传了图片）
  if (activeStep.value === 0) {
    activeStep.value++
    return
  }

  // 对于其他步骤，验证表单
  try {
    if (formRef.value) {
      await formRef.value.validate()
      activeStep.value++
    }
  } catch (error) {
    console.error('表单验证失败:', error)
    ElMessage.warning('请填写必填项')
  }
}

const handleCancel = () => {
  ElMessageBox.confirm('确定要取消添加吗？已填写的信息将会丢失', '提示', {
    confirmButtonText: '确定',
    cancelButtonText: '继续编辑',
    type: 'warning'
  }).then(() => {
    showAddDialog.value = false
    handleDialogClose()
  }).catch(() => {})
}

const handleDialogClose = () => {
  activeStep.value = 0
  isProcessing.value = false
  uploadFiles.value = []
  Object.assign(clothesForm, {
    id: '',
    name: '',
    category: '',
    subCategory: '',
    brand: '',
    color: '',
    colorName: '',
    season: '',
    occasions: [],
    style: '',
    material: '',
    image_url: '',
    description: '',
    thickness: '',
    hash: ''
  })
}

// 添加新的方法
const handleStepClick = (index: number) => {
  if (index < activeStep.value) {
    activeStep.value = index
  }
}

const removeImage = () => {
  clothesForm.image_url = ''
  aiAnalysis.value = null
}

// 修改获取季节名称的函数
const getSeasonName = (season: string): string => {
  const seasonMap: Record<string, string> = {
    'spring_and_autumn': '春秋季',
    'summer': '夏季',
    'autumn': '秋季',
    'all_season': '四季通用'
  }
  return seasonMap[season] || season
}

// 组件卸载时清理
onUnmounted(() => {
  isProcessing.value = false
  uploadFiles.value = []
})

// 修改 onMounted
onMounted(() => {
  getClosthesList()
})

const router = useRouter()

// 监听对话框显示状态
watch(showAddDialog, (newVal) => {
  if (newVal) {
    // 对话框打开时重置状态
    activeStep.value = dialogType.value === 'edit' ? 1 : 0  // 如果是编辑模式，直接跳到第二步
    isProcessing.value = false
    uploadFiles.value = []
    if (dialogType.value !== 'edit') {
      // 只有在新增模式下才清空表单
      aiAnalysis.value = null
      Object.assign(clothesForm, {
        id: '',
        name: '',
        category: '',
        subCategory: '',
        brand: '',
        color: '',
        colorName: '',
        season: '',
        occasions: [],
        style: '',
        material: '',
        image_url: '',
        description: '',
        thickness: '',
        hash: ''
      })
    }
  }
})

// 颜色系选项
const colorOptions = [
  { label: '红色系', value: '红色系' },
  { label: '黄色系', value: '黄色系' },
  { label: '绿色系', value: '绿色系' },
  { label: '蓝色系', value: '蓝色系' },
  { label: '紫色系', value: '紫色系' },
  { label: '黑色系', value: '黑色系' },
  { label: '白色系', value: '白色系' },
  { label: '灰色系', value: '灰色系' }
]
const subColorOptions = {
  '红色系': [
    { label: '粉红色', value: '粉红色' },
    { label: '朱红色', value: '朱红色' },
    { label: '大红色', value: '大红色' },
    { label: '玫瑰红', value: '玫瑰红' }
  ],
  '黄色系': [
    { label: '鹅黄色', value: '鹅黄色' },
    { label: '明黄色', value: '明黄色' },
    { label: '金黄色', value: '金黄色' }
  ],
  '绿色系': [
    { label: '中绿', value: '中绿' },
    { label: '橄榄绿', value: '橄榄绿' },
    { label: '墨绿色', value: '墨绿色' },
    { label: '黄绿色', value: '黄绿色' },
    { label: '孔雀绿', value: '孔雀绿' }
  ],
  '蓝色系': [
    { label: '藏蓝色', value: '藏蓝色' },
    { label: '青蓝色', value: '青蓝色' },
    { label: '天蓝色', value: '天蓝色' }
  ],
  '紫色系': [
    { label: '亮紫色', value: '亮紫色' },
    { label: '蓝紫色', value: '蓝紫色' },
    { label: '浅灰紫', value: '浅灰紫' }
  ],
  '黑色系': [
    { label: '黑色', value: '黑色' }
  ],
  '白色系': [
    { label: '白色', value: '白色' }
  ],
  '灰色系': [
    { label: '深灰色', value: '深灰色' },
    { label: '浅灰色', value: '浅灰色' }
  ]
}
const currentSubColorOptions = computed(() => {
  return subColorOptions[clothesForm.color] || []
})
watch(() => clothesForm.color, () => {
  clothesForm.subColor = ''
})

// 添加衣物方法
const handleAdd = () => {
  dialogType.value = 'add'
  Object.assign(clothesForm, {
    id: '',
    name: '',
    category: '',
    subCategory: '',
    brand: '',
    color: '',
    subColor: '',
    colorName: '',
    season: '',
    occasions: [],
    style: '',
    material: '',
    image_url: '',
    description: '',
    thickness: '',
    hash: ''
  })
  showAddDialog.value = true
}
</script>

<style scoped>
/* 全局容器样式 */
.wardrobe-container {
  padding: 16px;
  background-color: #f5f7fa;
  min-height: calc(100vh - 32px);
  max-width: 100%;
  overflow-x: hidden;
}

/* 统计卡片样式优化 - 修改为同一行显示 */
.statistics {
  display: flex;
  flex-direction: row;
  justify-content: space-between;
  margin-bottom: 24px;
  padding: 0 15px;
  gap: 20px;
}

.statistics .el-col {
  width: calc(33.333% - 14px);
  flex: 0 0 calc(33.333% - 14px);
  margin-bottom: 0;
}

.stat-card {
  display: flex;
  align-items: center;
  padding: 16px 20px;
  border-radius: 8px;
  transition: all 0.3s;
  height: 100%;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.05);
}

.stat-card:hover {
  transform: translateY(-3px);
  box-shadow: 0 4px 12px rgba(45, 90, 157, 0.15);
}

.stat-icon {
  font-size: 28px;
  color: #2d5a9d;
  margin-right: 16px;
  display: flex;
  align-items: center;
}

.stat-info {
  flex: 1;
}

.stat-title {
  font-size: 14px;
  color: #909399;
  margin-bottom: 6px;
}

.stat-number {
  font-size: 24px;
  font-weight: bold;
  color: #2d5a9d;
}

/* 操作栏样式 */
.operation-bar {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding: 16px;
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 2px 8px 0 rgba(0, 0, 0, 0.08);
  gap: 12px;
}

.operation-bar .left {
  margin-right: 16px;
}

.operation-bar .right {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: center;
}

.search-input {
  width: 200px;
  max-width: 100%;
}

.filter-select {
  width: 140px;
  max-width: 100%;
}

.add-button {
  padding: 9px 16px;
}

/* 衣物卡片布局修改 - 图片在左，标签在右 */
.clothes-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(500px, 1fr));
  gap: 16px;
  padding: 8px;
}

.clothes-card {
  width: 100%;
  height: auto;
  min-height: 200px;
  transition: transform 0.3s;
}

.clothes-card:hover {
  transform: translateY(-3px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.card-content {
  display: flex;
  flex-direction: row; /* 修改为水平布局 */
  height: 100%;
  align-items: center;
}

.image-wrapper {
  position: relative;
  width: 200px; /* 固定宽度 */
  height: 200px;
  flex-shrink: 0;
  overflow: hidden;
  border-radius: 4px 0 0 4px;
}

.clothes-image {
  width: 100%;
  height: 100%;
  object-fit: contain;
  transition: transform 0.3s;
}

.clothes-card:hover .clothes-image {
  transform: scale(1.05);
}

.image-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: #f5f7fa;
  font-size: 32px;
  color: #dcdfe6;
}

.image-overlay {
  position: absolute;
  top: 8px;
  right: 8px;
  opacity: 0;
  transition: opacity 0.3s;
  z-index: 2;
}

.clothes-card:hover .image-overlay {
  opacity: 1;
}

.action-button {
  padding: 6px;
}

.clothes-info {
  flex: 1;
  padding: 15px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  overflow: hidden;
}

.clothes-info h3 {
  margin: 0;
  font-size: 16px;
  color: #303133;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 4px;
}

.tags .el-tag {
  margin-right: 4px;
  margin-bottom: 4px;
}

.occasion-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 4px;
}

.details {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  font-size: 13px;
}

.detail-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 6px;
}

.detail-row p {
  margin: 0;
  flex: 1;
  min-width: calc(50% - 8px);
  font-size: 13px;
  color: #606266;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.detail-row span {
  color: #909399;
  margin-right: 4px;
}

/* 对话框和表单样式保持不变 */
/* ... */

/* 响应式调整 */
@media (max-width: 1200px) {
  .clothes-grid {
    grid-template-columns: repeat(auto-fill, minmax(450px, 1fr));
  }
}

@media (max-width: 992px) {
  .clothes-grid {
    grid-template-columns: repeat(auto-fill, minmax(400px, 1fr));
  }
}

@media (max-width: 768px) {
  /* 小屏幕时统计卡片改为垂直布局 */
  .statistics {
    flex-direction: column;
    gap: 15px;
  }
  
  .statistics .el-col {
    width: 100%;
    flex: 0 0 100%;
    margin-bottom: 10px;
  }
  
  .clothes-grid {
    grid-template-columns: 1fr;
  }
  
  .card-content {
    flex-direction: column;
  }
  
  .image-wrapper {
    width: 100%;
    height: 200px;
    border-radius: 4px 4px 0 0;
  }
}

@media (max-width: 576px) {
  .wardrobe-container {
    padding: 12px;
  }
  
  .operation-bar {
    flex-direction: column;
    align-items: stretch;
  }
  
  .operation-bar .left,
  .operation-bar .right {
    width: 100%;
    margin-right: 0;
  }
  
  .operation-bar .right {
    flex-direction: column;
    align-items: stretch;
  }
  
  .search-input,
  .filter-select {
    width: 100%;
  }
  
  .image-wrapper {
    height: 180px;
  }
}

/* Mac 特定优化 */
@media screen and (-webkit-min-device-pixel-ratio: 2) {
  .wardrobe-container {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
  }
  
  .el-form-item__label,
  .el-input__inner,
  .el-select-dropdown__item,
  .el-button {
    font-weight: 400;
  }
  
  /* 优化Mac Retina显示屏的锐利度 */
  .clothes-card,
  .stat-card,
  .operation-bar {
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
    border-radius: 6px;
  }
  
  /* 为Mac调整的颜色和对比度 */
  .clothes-info h3 {
    color: #262626;
  }
  
  .detail-row p {
    color: #595959;
  }
  
  .detail-row span {
    color: #8c8c8c;
  }
}

.steps-sidebar {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.step-item {
  display: flex;
  align-items: center;
  padding: 10px;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.3s;
}

.step-item:hover {
  background-color: #f0f0f0;
}

.step-icon {
  font-size: 20px;
  color: #909399;
  margin-right: 10px;
}

.step-info {
  flex: 1;
}

.step-title {
  font-size: 14px;
  font-weight: bold;
  color: #303133;
}

.step-desc {
  font-size: 12px;
  color: #909399;
}

.active {
  background-color: #2d5a9d;
}

.active .step-icon {
  color: white;
}

.active .step-title {
  color: white;
}

.active .step-desc {
  color: white;
}

.form-content {
  display: flex;
  gap: 20px;
}

.step-form {
  flex: 1;
  padding: 20px;
  background: #f8f9fa;
  border-radius: 8px;
}

.upload-container {
  text-align: center;
  padding: 20px;
}

.preview-area {
  width: 100%;
  height: 300px;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  overflow: hidden;
  position: relative;
  background: #f8f9fa;
  margin-bottom: 20px;
}

.preview-image {
  width: 100%;
  height: 100%;
  background: transparent;
}

.preview-actions {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.5);
  opacity: 0;
  transition: all 0.3s;
}

.preview-actions:hover {
  opacity: 1;
}

.upload-area {
  width: 100%;
  border: 2px dashed #dcdfe6;
  border-radius: 8px;
  cursor: pointer;
  position: relative;
  overflow: hidden;
  transition: all 0.3s;
}

.upload-area:hover {
  border-color: #2d5a9d;
}

.upload-content {
  padding: 40px 0;
  text-align: center;
}

.upload-icon {
  font-size: 48px;
  color: #909399;
  margin-bottom: 16px;
}

.processing-mask {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(255, 255, 255, 0.9);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}

.processing-icon {
  font-size: 32px;
  color: #2d5a9d;
  animation: rotating 2s linear infinite;
}

@keyframes rotating {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.upload-tips {
  margin-top: 10px;
  color: #909399;
  font-size: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
}

.tip-item {
  display: flex;
  align-items: center;
  gap: 5px;
}

.color-select {
  display: flex;
  align-items: center;
  gap: 15px;
}

.season-select {
  display: flex;
  justify-content: space-between;
}

.occasion-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
}

.dialog-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
