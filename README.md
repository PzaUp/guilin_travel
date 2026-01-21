# 桂林旅游推荐系统

## 前端模块
负责 UI 渲染与交互，按“单页应用”方式组织，通过 fetch 调用 RESTful 接口。核心脚本全部内嵌于 index.html，便于教学演示与一键部署。

## 后端模块（app.py）
统一路由，核心职责：

(1)用户鉴权（注册/登录/会话/修改密码）

(2)攻略管理（发布/查询/点赞/回复）

(3)POI 收藏（新增/取消）

(4)静态资源代理（特色美食图片）

## 数据库模块
关系型存储，共 5 张表：user_info、travel_guides、user_favorite_poi、guide_likes、guide_replies。通过 pyodbc 连接池与后端交互。
