<template>
  <div class="layout-container">
    <div class="sidebar" :class="{ collapsed: isCollapsed }">
      <div class="logo">
        <h2 v-if="!isCollapsed">服饰推荐系统</h2>
        <span v-else class="iconfont">hello</span>
      </div>
      <el-menu
        :collapse="isCollapsed"
        :default-active="route.path"
        router
        class="custom-menu"
      >
        <el-menu-item index="/dashboard">
          <el-icon><DataBoard /></el-icon>
          <template #title>我的数据</template>
        </el-menu-item>
        <el-menu-item index="/wardrobe">
          <el-icon><Suitcase /></el-icon>
          <template #title>我的衣橱</template>
        </el-menu-item>
        <el-menu-item index="/recommend">
          <el-icon><Connection /></el-icon>
          <template #title>服装推荐</template>
        </el-menu-item>
        <el-menu-item index="/favorite">
          <el-icon><Star /></el-icon>
          <template #title>我的穿搭</template>
        </el-menu-item>
      </el-menu>
    </div>
    
    <div class="main-container">
      <div class="header">
        <el-icon 
          class="collapse-btn"
          @click="toggleCollapse"
        >
          <Fold v-if="!isCollapsed"/>
          <Expand v-else/>
        </el-icon>
        
        <div class="header-right">
          <el-dropdown>
            <span class="user-info">
              {{ userInfo.username }}
              <el-icon><ArrowDown /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item @click="handleLogout">退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </div>
      
      <div class="content">
        <router-view></router-view>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  DataBoard,
  Suitcase,
  Star,
  Fold,
  Expand,
  ArrowDown,
  Connection
} from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()
const isCollapsed = ref(false)
const userInfo = ref({
  username: ''
})

const toggleCollapse = () => {
  isCollapsed.value = !isCollapsed.value
}

const handleLogout = () => {
  localStorage.removeItem('user')
  localStorage.removeItem('loginInfo')
  router.push('/login')
  ElMessage.success('已安全退出')
}

onMounted(() => {
  const userStr = localStorage.getItem('user')
  if (userStr) {
    userInfo.value = JSON.parse(userStr)
  }
})
</script>

<style scoped>
.layout-container {
  height: 100vh;
  display: flex;
}

.sidebar {
  width: 240px;
  height: 100%;
  background: linear-gradient(180deg, #2d5a9d 0%, #1e3c6e 100%);
  transition: all 0.3s;
  overflow: hidden;
  box-shadow: 2px 0 10px rgba(0, 0, 0, 0.1);
}

.sidebar.collapsed {
  width: 64px;
}

.logo {
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 20px;
  background: rgba(255, 255, 255, 0.1);
  margin-bottom: 10px;
}

.logo h2 {
  margin: 0;
  font-size: 20px;
}

.logo .iconfont {
  font-size: 24px;
}

:deep(.custom-menu) {
  border-right: none;
  background: transparent;
}

:deep(.el-menu) {
  border-right: none;
}

:deep(.el-menu-item) {
  background: transparent !important;
  color: rgba(255, 255, 255, 0.8) !important;
  height: 50px;
  line-height: 50px;
  margin: 8px 0;
}

:deep(.el-menu-item:hover) {
  color: white !important;
  background: rgba(255, 255, 255, 0.1) !important;
}

:deep(.el-menu-item.is-active) {
  color: white !important;
  background: rgba(255, 255, 255, 0.2) !important;
  &::before {
    content: '';
    position: absolute;
    left: 0;
    top: 0;
    width: 4px;
    height: 100%;
    background: white;
  }
}

.main-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background-color: #f5f7fa;
}

.header {
  height: 60px;
  background: white;
  border-bottom: 1px solid rgba(45, 90, 157, 0.2);
  display: flex;
  align-items: center;
  padding: 0 20px;
  justify-content: space-between;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.05);
}

.collapse-btn {
  font-size: 20px;
  cursor: pointer;
  color: #2d5a9d;
  transition: all 0.3s;
}

.collapse-btn:hover {
  transform: scale(1.1);
}

.header-right {
  display: flex;
  align-items: center;
}

.user-info {
  display: flex;
  align-items: center;
  cursor: pointer;
  color: #666;
  transition: all 0.3s;
  padding: 5px 10px;
  border-radius: 15px;
}

.user-info:hover {
  background: rgba(45, 90, 157, 0.1);
  color: #2d5a9d;
}

.content {
  flex: 1;
  padding: 20px;
  overflow: auto;
}

:deep(.el-dropdown-menu__item:hover) {
  background-color: rgba(45, 90, 157, 0.1);
  color: #2d5a9d;
}
</style> 