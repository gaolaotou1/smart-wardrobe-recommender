<template>
  <div class="login-container">
    <div class="login-content">
      <div class="left-panel">
        <div class="welcome-text">
          <h1>欢迎使用</h1>
          <h2>服饰穿搭推荐系统</h2>
          <p>Fashion Style Recommendation System</p>
        </div>
      </div>
      <div class="right-panel">
        <!-- 登录表单 -->
        <div v-if="!showRegister" class="login-form">
          <h3>账号登录</h3>
          <div class="input-group">
            <input 
              type="text" 
              v-model="loginForm.username" 
              placeholder="请输入用户名"
            >
          </div>
          <div class="input-group">
            <input 
              type="password" 
              v-model="loginForm.password" 
              placeholder="请输入密码"
            >
          </div>
          <div class="options">
            <label class="remember">
              <input type="checkbox" v-model="loginForm.remember">
              <span>记住我</span>
            </label>
            <a href="#" class="forget">忘记密码？</a>
          </div>
          <button class="submit-btn" @click="handleLogin">
            登录
          </button>
          <div class="switch-form">
            还没有账号？<a href="#" @click.prevent="showRegister = true">立即注册</a>
          </div>
        </div>

        <!-- 注册表单 -->
        <div v-else class="register-form">
          <h3>账号注册</h3>
          <div class="input-group">
            <input 
              type="text" 
              v-model="registerForm.username" 
              placeholder="请输入用户名（4-20个字符）"
            >
          </div>
          <div class="input-group">
            <input 
              type="password" 
              v-model="registerForm.password" 
              placeholder="请输入密码（6-20个字符）"
            >
          </div>
          <div class="input-group">
            <input 
              type="password" 
              v-model="registerForm.confirmPassword" 
              placeholder="请确认密码"
            >
          </div>
          <button class="submit-btn" @click="handleRegister">
            注册
          </button>
          <div class="switch-form">
            已有账号？<a href="#" @click.prevent="showRegister = false">返回登录</a>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script lang="ts" setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import { ElMessage } from 'element-plus'

const router = useRouter()
const showRegister = ref(false)
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || ''

const loginForm = reactive({
  username: '',
  password: '',
  remember: false
})

const registerForm = reactive({
  username: '',
  password: '',
  confirmPassword: ''
})

// 登录处理
const handleLogin = async () => {
  // 表单验证
  if (!loginForm.username || !loginForm.password) {
    ElMessage.warning('请输入用户名和密码')
    return
  }

  try {
    const res = await axios.post(`${API_BASE_URL}/api/login`, {
      username: loginForm.username,
      password: loginForm.password
    })
    
    if (res.data.code === 200) {
      ElMessage({
        message: '登录成功，欢迎回来！',
        type: 'success',
        duration: 2000
      })
      
      // 存储用户信息
      localStorage.setItem('user', JSON.stringify(res.data.data))
      localStorage.setItem('userId', res.data.data.id)
      localStorage.setItem('token', res.data.data.token)
      
      // 记住登录信息
      if (loginForm.remember) {
        localStorage.setItem('loginInfo', JSON.stringify({
          username: loginForm.username,
          remember: true
        }))
      } else {
        localStorage.removeItem('loginInfo')
      }
      
      setTimeout(() => {
        router.push('/')
      }, 1000)
    } else {
      ElMessage.error(res.data.message)
    }
  } catch (error) {
    console.error('登录失败:', error)
    ElMessage.error('登录失败，请检查网络连接')
  }
}

// 注册处理
const handleRegister = async () => {
  // 表单验证
  if (!registerForm.username || !registerForm.password || !registerForm.confirmPassword) {
    ElMessage.warning('请填写完整注册信息')
    return
  }

  if (registerForm.username.length < 4 || registerForm.username.length > 20) {
    ElMessage.warning('用户名长度应为4-20个字符')
    return
  }

  if (registerForm.password.length < 6 || registerForm.password.length > 20) {
    ElMessage.warning('密码长度应为6-20个字符')
    return
  }

  if (registerForm.password !== registerForm.confirmPassword) {
    ElMessage.warning('两次输入的密码不一致')
    return
  }

  try {
    const res = await axios.post(`${API_BASE_URL}/api/register`, {
      username: registerForm.username,
      password: registerForm.password
    })
    
    if (res.data.code === 200) {
      ElMessage({
        message: '注册成功！',
        type: 'success',
        duration: 2000
      })
      
      // 清空注册表单
      registerForm.username = ''
      registerForm.password = ''
      registerForm.confirmPassword = ''
      
      // 切换到登录页
      showRegister.value = false
    } else {
      ElMessage.error(res.data.message)
    }
  } catch (error) {
    console.error('注册失败:', error)
    ElMessage.error('注册失败，请检查网络连接')
  }
}

// 检查保存的登录信息
const checkSavedLogin = () => {
  const savedLogin = localStorage.getItem('loginInfo')
  if (savedLogin) {
    const { username, remember } = JSON.parse(savedLogin)
    loginForm.username = username
    loginForm.remember = remember
  }
}

checkSavedLogin()
</script>

<style scoped>
.login-container {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #2d5a9d 0%, #1e3c6e 100%);
  padding: 20px;
}

.login-content {
  display: flex;
  width: 1000px;
  height: 600px;
  background: white;
  border-radius: 20px;
  overflow: hidden;
  box-shadow: 0 15px 30px rgba(0,0,0,0.1);
}

.left-panel {
  flex: 1;
  background: linear-gradient(135deg, #3468b5 0%, #2d5a9d 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px;
}

.welcome-text {
  text-align: center;
  color: white;
}

.welcome-text h1 {
  font-size: 36px;
  margin-bottom: 20px;
  font-weight: 600;
}

.welcome-text h2 {
  font-size: 28px;
  margin-bottom: 15px;
}

.welcome-text p {
  font-size: 16px;
  opacity: 0.9;
}

.right-panel {
  flex: 1;
  padding: 60px;
  display: flex;
  align-items: center;
}

.login-form, .register-form {
  width: 100%;
}

.login-form h3, .register-form h3 {
  font-size: 24px;
  color: #333;
  margin-bottom: 40px;
  text-align: center;
}

.input-group {
  position: relative;
  margin-bottom: 30px;
}

.input-group input {
  width: 100%;
  padding: 15px;
  border: 2px solid #eee;
  border-radius: 10px;
  font-size: 16px;
  transition: all 0.3s ease;
}

.input-group input:focus {
  border-color: #2d5a9d;
  outline: none;
}

.options {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 30px;
}

.remember {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #666;
}

.forget {
  color: #2d5a9d;
  text-decoration: none;
  font-size: 14px;
}

.submit-btn {
  width: 100%;
  padding: 15px;
  background: linear-gradient(135deg, #2d5a9d 0%, #1e3c6e 100%);
  border: none;
  border-radius: 10px;
  color: white;
  font-size: 16px;
  cursor: pointer;
  transition: all 0.3s ease;
}

.submit-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 5px 15px rgba(45, 90, 157, 0.4);
}

.switch-form {
  margin-top: 20px;
  text-align: center;
  color: #666;
}

.switch-form a {
  color: #2d5a9d;
  text-decoration: none;
  margin-left: 5px;
}

.switch-form a:hover {
  text-decoration: underline;
}

@media (max-width: 768px) {
  .login-content {
    flex-direction: column;
    width: 100%;
    height: auto;
  }
  
  .left-panel {
    padding: 40px 20px;
  }
  
  .right-panel {
    padding: 40px 20px;
  }
}
</style> 
