// 衣物项类型
export interface ClothesItem {
  id: number;
  name: string;
  description?: string;
  image_url: string;
  category: string;
  brand?: string;
  style?: string;
  color?: string;
  colorName?: string;
  season: string;
  material?: string;
  occasions?: string[];
  tags?: string[];
  createdAt?: string;
  updatedAt?: string;
}

// 穿搭类型
export interface Outfit {
  id: number;
  name: string;
  description?: string;
  clothes: ClothesItem[];
  createdAt?: string;
  updatedAt?: string;
}

// API响应类型
export interface ApiResponse<T> {
  code: number;
  data: T;
  message?: string;
}

// 筛选条件类型
export interface Filters {
  keyword: string;
  category: string;
  season: string;
  occasion: string;
}

// 分类类型
export interface Category {
  id: number;
  name: string;
  description?: string;
}

// 场合标签类型
export interface OccasionTag {
  id: number;
  name: string;
  description?: string;
}

// 衣物表单类型
export interface ClothesForm {
  id: string | number;
  name: string;
  categories: string[];
  brand: string;
  color: string;
  colorName: string;
  season: string;
  occasions: string[];
  style: string;
  material: string;
  image_url: string;
  description: string;
}

// AI分析结果类型
export interface AIAnalysis {
  category: string;
  style: string;
  color: string;
  season: string;
  material: string;
  occasions: string[];
  description: string;
}

// 步骤类型
export interface Step {
  title: string;
  desc: string;
}

// 聊天消息类型
export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

// 推荐请求类型
export interface RecommendRequest {
  clothes: {
    id: number;
    name: string;
    category: string;
    style?: string;
    color?: string;
    season: string;
    material?: string;
    occasions?: string[];
    description?: string;
  }[];
  question: string;
} 