<template>
  <div class="dashboard-container">
    <!-- 统计卡片 -->
    <el-row :gutter="20">
      <el-col :span="6" v-for="card in cards" :key="card.title">
        <el-card class="data-card" :body-style="{ padding: '10px' }">
          <div class="card-header">
            <span>{{ card.title }}</span>
            <el-icon class="card-icon" :style="{ color: '#2d5a9d' }">
              <component :is="card.icon" />
            </el-icon>
          </div>
          <div class="card-number">{{ card.number }}</div>
          <div class="card-footer">{{ card.desc }}</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 图表区域 -->
    <el-row :gutter="20" class="chart-row" v-if="currentPage === 1">
      <el-col :span="12">
        <el-card class="chart-card">
          <template #header>
            <div class="card-title">
              <span>衣物分类统计</span>
              <el-tooltip content="展示各类衣物的数量分布" placement="top">
                <el-icon><InfoFilled /></el-icon>
              </el-tooltip>
            </div>
          </template>
          <div ref="pieChart" class="chart"></div>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card class="chart-card">
          <template #header>
            <div class="card-title">
              <span>季节分布</span>
              <el-tooltip content="展示各季节衣物的数量分布" placement="top">
                <el-icon><InfoFilled /></el-icon>
              </el-tooltip>
            </div>
          </template>
          <div ref="seasonChart" class="chart"></div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" class="chart-row" v-else-if="currentPage === 2">
      <el-col :span="12">
        <el-card class="chart-card">
          <template #header>
            <div class="card-title">
              <span>上装类别分布</span>
              <el-tooltip content="展示各类上装的数量分布" placement="top">
                <el-icon><InfoFilled /></el-icon>
              </el-tooltip>
            </div>
          </template>
          <div ref="topChart" class="chart"></div>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card class="chart-card">
          <template #header>
            <div class="card-title">
              <span>下装类别分布</span>
              <el-tooltip content="展示各类下装的数量分布" placement="top">
                <el-icon><InfoFilled /></el-icon>
              </el-tooltip>
            </div>
          </template>
          <div ref="bottomChart" class="chart"></div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" class="chart-row" v-else-if="currentPage === 3">
      <el-col :span="14">
        <el-card class="chart-card">
          <template #header>
            <div class="card-title">
              <span>近期穿搭记录</span>
              <el-tooltip content="展示最近7天的穿搭创建趋势" placement="top">
                <el-icon><InfoFilled /></el-icon>
              </el-tooltip>
            </div>
          </template>
          <div ref="trendChart" class="chart"></div>
        </el-card>
      </el-col>
      <el-col :span="10">
        <el-card class="outfit-card">
          <template #header>
            <div class="card-title">
              <span>最新穿搭</span>
              <el-tooltip content="展示最近创建的穿搭" placement="top">
                <el-icon><InfoFilled /></el-icon>
              </el-tooltip>
            </div>
          </template>
          <el-empty v-if="!recentOutfits.length" description="暂无穿搭记录" />
          <el-carousel v-else height="250px" :interval="4000" indicator-position="outside">
            <el-carousel-item v-for="item in recentOutfits" :key="item.date">
              <div class="outfit-item">
                <div class="outfit-image">
                  <el-image 
                    :src="item.image" 
                    fit="cover"
                    :preview-src-list="[item.image]"
                  >
                    <template #error>
                      <div class="image-placeholder">
                        <el-icon><Picture /></el-icon>
                      </div>
                    </template>
                  </el-image>
                </div>
                <div class="outfit-info">
                  <h4>{{ item.title }}</h4>
                  <p class="date">{{ item.date }}</p>
                  <p class="desc">{{ item.desc }}</p>
                  <div class="tags">
                    <el-tag 
                      v-for="tag in item.tags" 
                      :key="tag" 
                      size="small"
                      :style="{ backgroundColor: 'rgba(45, 90, 157, 0.1)', color: '#2d5a9d', borderColor: '#2d5a9d' }"
                    >
                      {{ tag }}
                    </el-tag>
                  </div>
                </div>
              </div>
            </el-carousel-item>
          </el-carousel>
        </el-card>
      </el-col>
    </el-row>

    <!-- 翻页按钮 -->
    <div class="dashboard-nav">
      <el-button @click="prevPage" :disabled="currentPage === 1" icon="ArrowLeft" circle />
      <span class="page-indicator">第 {{ currentPage }} 页 / 3</span>
      <el-button @click="nextPage" :disabled="currentPage === 3" icon="ArrowRight" circle />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, reactive, nextTick, watch } from 'vue'
import * as echarts from 'echarts'
import axios from 'axios'
import { ElMessage } from 'element-plus'
import {
  Goods,
  Calendar,
  Collection,
  Star,
  InfoFilled,
  Picture,
  ArrowLeft,
  ArrowRight
} from '@element-plus/icons-vue'

// 添加axios基础URL配置
axios.defaults.baseURL = import.meta.env.VITE_API_BASE_URL || ''

// 定义接口返回的数据类型
interface DashboardData {
  statistics: {
    totalClothes: number
    monthlyOutfits: number
    monthly_newClothesCount: number
    styleCount: number
  }
  categoryDistribution: {
    name: string
    value: number
  }[]
  weeklyTrend: {
    date: string
    count: number
  }[]
  recentOutfits: {
    date: string
    title: string
    desc: string
    image: string
    tags: string[]
  }[]
  seasonStats: {
    season: string
    count: number
  }[]
  sub_categoryDistribution: {
    sub_category: string
    count: number
  }[]
  sub_categoryDistribution1: {
    sub_category: string
    count: number
  }[]
}

// 初始化数据
const cards = reactive([
  {
    title: '衣物总数',
    number: '0',
    desc: '件衣物',
    icon: Goods
  },
  {
    title: '本月搭配',
    number: '0',
    desc: '次穿搭',
    icon: Calendar
  },
  {
    title: '本月新增',
    number: '0',
    desc: '件衣物',
    icon: Collection
  },
  {
    title: '风格数量',
    number: '0',
    desc: '种风格',
    icon: Star
  }
])

const recentOutfits = ref<DashboardData['recentOutfits']>([])
const trendChart = ref<HTMLElement>()
const pieChart = ref<HTMLElement>()
const seasonChart = ref<HTMLElement>()
const topChart = ref<HTMLElement>()
const bottomChart = ref<HTMLElement>()
const dashboardData = ref<DashboardData | null>(null)

const currentPage = ref(1)
function prevPage() {
  if (currentPage.value > 1) currentPage.value--
}
function nextPage() {
  if (currentPage.value < 3) currentPage.value++
}

// 获取仪表盘数据
const getDashboardData = async () => {
  try {
    const userId = localStorage.getItem('userId')
    if (!userId) {
      ElMessage.warning('请先登录')
      return
    }
    const res = await axios.get(`/api/dashboard?user_id=${userId}`)
    if (res.data.code === 200) {
      const data = res.data.data as DashboardData
      dashboardData.value = data
      // 更新卡片数据
      cards[0].number = data.statistics.totalClothes.toString()
      cards[1].number = data.statistics.monthlyOutfits.toString()
      cards[2].number = data.statistics.monthly_newClothesCount.toString()
      cards[3].number = data.statistics.styleCount.toString()
      // 更新推荐数据
      recentOutfits.value = data.recentOutfits
      // 默认只初始化第一页图表
      await nextTick()
      updatePage1Charts(data)
    }
  } catch (error) {
    console.error('获取仪表盘数据失败:', error)
    ElMessage.error('获取数据失败')
  }
}

// 只更新第一页图表
const updatePage1Charts = (data: DashboardData) => {
  if (!pieChart.value || !seasonChart.value) return
  // 分类饼图
  const pie = echarts.init(pieChart.value)
  pie.setOption({
    tooltip: {
      trigger: 'item',
      formatter: '{b}: {c}件 ({d}%)'
    },
    legend: {
      orient: 'vertical',
      right: 10,
      top: 'center',
      textStyle: { color: '#606266' }
    },
    series: [
      {
        name: '衣物分类',
        type: 'pie',
        radius: ['40%', '70%'],
        avoidLabelOverlap: false,
        itemStyle: {
          borderRadius: 10,
          borderColor: '#fff',
          borderWidth: 2
        },
        label: { show: false },
        emphasis: {
          label: { show: true, fontSize: 14, fontWeight: 'bold' }
        },
        color: ['#2d5a9d', '#3468b5', '#4a90e2', '#64b5f6', '#90caf9', '#bbdefb'],
        data: data.categoryDistribution
      }
    ]
  })
  // 季节分布饼图
  const season = echarts.init(seasonChart.value)
  const seasonNames = {
    'spring_and_autumn': '春秋季',
    'summer': '夏季',
    'winter': '冬季',
    'all_season': '四季通用'
  }
  const seasonColors = {
    'spring_and_autumn': '#95e1d3',
    'summer': '#f08a5d',
    'winter': '#b83b5e',
    'all_season': '#6c5b7b'
  }
  season.setOption({
    tooltip: {
      trigger: 'item',
      formatter: '{b}: {c}件 ({d}%)'
    },
    legend: {
      orient: 'vertical',
      left: 10,
      top: 'center',
      textStyle: { color: '#606266' }
    },
    series: [
      {
        type: 'pie',
        radius: '50%',
        center: ['50%', '50%'], // 确保图表居中
        data: data.seasonStats.map((item: any) => ({
          name: seasonNames[item.season] || item.season,
          value: item.count,
          itemStyle: { color: seasonColors[item.season] || '#999' }
        })),
        emphasis: {
          itemStyle: {
            shadowBlur: 10,
            shadowOffsetX: 0,
            shadowColor: 'rgba(0, 0, 0, 0.5)'
          }
        }
      }
    ]
  })
  
  // 确保图表响应窗口调整
  window.addEventListener('resize', () => {
    pie.resize()
    season.resize()
  })
}

// 只更新第二页图表
const updatePage2Charts = (data: DashboardData) => {
  if (!topChart.value || !bottomChart.value) return
  const top = echarts.init(topChart.value)
  const bottom = echarts.init(bottomChart.value)
  
  // 上装类别分布
  top.setOption({
    tooltip: {
      trigger: 'item',
      formatter: '{b}: {c}件 ({d}%)'
    },
    legend: {
      orient: 'vertical',
      left: 10,
      top: 'center',
      textStyle: { color: '#606266' }
    },
    series: [
      {
        type: 'pie',
        radius: '50%',
        center: ['50%', '50%'], // 确保图表居中
        data: data.sub_categoryDistribution.map(item => ({
          name: item.sub_category,
          value: item.count
        })),
        emphasis: {
          itemStyle: {
            shadowBlur: 10,
            shadowOffsetX: 0,
            shadowColor: 'rgba(0, 0, 0, 0.5)'
          }
        }
      }
    ]
  })
  
  // 下装类别分布
  bottom.setOption({
    tooltip: {
      trigger: 'item',
      formatter: '{b}: {c}件 ({d}%)'
    },
    legend: {
      orient: 'vertical',
      right: 10,
      top: 'center',
      textStyle: { color: '#606266' }
    },
    series: [
      {
        type: 'pie',
        radius: '50%',
        center: ['50%', '50%'], // 确保图表居中
        data: data.sub_categoryDistribution1.map(item => ({
          name: item.sub_category,
          value: item.count
        })),
        emphasis: {
          itemStyle: {
            shadowBlur: 10,
            shadowOffsetX: 0,
            shadowColor: 'rgba(0, 0, 0, 0.5)'
          }
        }
      }
    ]
  })
  
  // 确保图表响应窗口调整
  window.addEventListener('resize', () => {
    top.resize()
    bottom.resize()
  })
}

// 只更新第三页图表
const updatePage3Charts = (data: DashboardData) => {
  if (!trendChart.value) return
  const trend = echarts.init(trendChart.value)
  trend.setOption({
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' }
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: data.weeklyTrend.map((item: any) => item.date),
      axisLabel: { color: '#606266' },
      axisLine: { lineStyle: { color: '#dcdfe6' } }
    },
    yAxis: {
      type: 'value',
      name: '搭配数量',
      nameTextStyle: { color: '#606266' },
      axisLabel: { color: '#606266' },
      axisLine: { lineStyle: { color: '#dcdfe6' } },
      splitLine: { lineStyle: { color: '#ebeef5' } }
    },
    series: [{
      data: data.weeklyTrend.map((item: any) => item.count),
      type: 'line',
      smooth: true,
      showSymbol: true,
      symbolSize: 8,
      areaStyle: {
        opacity: 0.3,
        color: {
          type: 'linear',
          x: 0,
          y: 0,
          x2: 0,
          y2: 1,
          colorStops: [
            { offset: 0, color: '#2d5a9d' },
            { offset: 1, color: 'rgba(45, 90, 157, 0.1)' }
          ]
        }
      },
      itemStyle: { color: '#2d5a9d', borderColor: '#fff', borderWidth: 2 },
      lineStyle: { color: '#2d5a9d', width: 3 }
    }]
  })
  
  // 确保图表响应窗口调整
  window.addEventListener('resize', () => {
    trend.resize()
  })
}

// 监听 currentPage，切换时初始化对应图表
watch(currentPage, async (val) => {
  await nextTick()
  if (!dashboardData.value) return
  if (val === 1) {
    updatePage1Charts(dashboardData.value)
  } else if (val === 2) {
    updatePage2Charts(dashboardData.value)
  } else if (val === 3) {
    updatePage3Charts(dashboardData.value)
  }
})

onMounted(() => {
  getDashboardData()
})
</script>

<style scoped>
.dashboard-container {
  padding: 8px;
  background-color: #f5f7fa;
  min-height: 100vh;
  max-height: 100vh;
  overflow-y: auto;
}

.data-card {
  margin-bottom: 10px;
  border-radius: 12px;
  overflow: hidden;
  transition: all 0.3s ease;
  background: #fff;
  border: 1px solid rgba(45, 90, 157, 0.1);
  height: 100px; /* 更小的卡片高度 */
}

.data-card:hover {
  transform: translateY(-3px);
  box-shadow: 0 5px 15px rgba(45, 90, 157, 0.1);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 2px;
  color: #606266;
}

.card-icon {
  font-size: 18px; /* 减小图标 */
}

.card-number {
  font-size: 20px;
  font-weight: bold;
  margin: 5px 0;
  background: linear-gradient(135deg, #2d5a9d 0%, #3468b5 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.card-footer {
  color: #909399;
  font-size: 12px;
}

.chart-row {
  margin-top: 8px;
  margin-bottom: 8px;
  height: calc(100vh - 180px); /* 适应视口高度 */
  max-height: 450px; /* 限制最大高度 */
  display: flex;
}

.chart-card, .outfit-card {
  border-radius: 12px;
  overflow: hidden;
  transition: all 0.3s ease;
  border: 1px solid rgba(45, 90, 157, 0.1);
  height: 100%;
  display: flex;
  flex-direction: column;
}

.chart-card:hover, .outfit-card:hover {
  box-shadow: 0 5px 15px rgba(45, 90, 157, 0.1);
}

.card-title {
  font-size: 15px;
  font-weight: bold;
  color: #303133;
  display: flex;
  align-items: center;
  gap: 8px;
}

.chart {
  height: 100%;
  width: 100%;
  padding: 5px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.outfit-item {
  padding: 8px;
  height: 100%;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.outfit-image {
  width: 100%;
  border-radius: 8px;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: #f5f7fa;
  height: 130px; /* 减小图片高度 */
}

.outfit-image :deep(.el-image) {
  width: 100%;
  height: 100%;
}

.outfit-image :deep(.el-image__inner) {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.outfit-image :deep(.el-image__error) {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f5f7fa;
  color: #909399;
  font-size: 30px;
}

.outfit-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 0;
  overflow-y: auto;
}

.outfit-info h4 {
  margin: 0;
  font-size: 15px;
  color: #303133;
}

.outfit-info .date {
  color: #909399;
  font-size: 12px;
  margin: 0;
}

.outfit-info .desc {
  color: #606266;
  font-size: 12px;
  line-height: 1.3;
  margin: 0;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.tags {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
  margin-top: 3px;
}

:deep(.el-card__header) {
  padding: 8px 12px; /* 减小内边距 */
  border-bottom: 1px solid #ebeef5;
  background: linear-gradient(135deg, rgba(45, 90, 157, 0.05) 0%, rgba(30, 60, 110, 0.05) 100%);
}

:deep(.el-carousel__indicators) {
  bottom: -5px;
}

:deep(.el-carousel__indicator--horizontal) {
  padding: 6px 3px;
}

:deep(.el-carousel__button) {
  width: 18px;
  height: 3px;
  background-color: rgba(45, 90, 157, 0.3);
}

:deep(.el-carousel__indicator.is-active .el-carousel__button) {
  background-color: #2d5a9d;
}

.dashboard-nav {
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 5px 0 10px 0;
  gap: 15px;
}

.page-indicator {
  font-size: 15px;
  color: #2d5a9d;
  font-weight: bold;
}

:deep(.el-card__body) {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  padding: 0;
}

:deep(.el-carousel__container) {
  height: 100%;
}

:deep(.el-carousel__item) {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.el-carousel {
  height: 100%;
  margin-bottom: 5px;
}

.outfit-card {
  height: 100%;
  display: flex;
  flex-direction: column;
}


@media screen and (max-height: 800px) {
  .data-card {
    height: 100px;
    margin-bottom: 40px;
  }
  
  .chart-row {
    height: calc(100vh - 160px);
    max-height: 400px;
  }
  
  .outfit-image {
    height: 120px;
  }
  
  .dashboard-nav {
    margin: 3px 0 8px 0;
  }
  
  :deep(.el-card__header) {
    padding: 6px 10px;
  }
  
  .card-title {
    font-size: 14px;
  }
  
  .card-number {
    font-size: 18px;
    margin: 3px 0;
  }
}
</style>
