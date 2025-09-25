import httpx
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger

# 用于渲染天气图片的 HTML + Jinja2 模板
WEATHER_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>天气信息</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@400;700&display=swap');
        body {
            font-family: 'Noto Sans SC', sans-serif;
            background: linear-gradient(135deg, {{ weather.weather_colors[0] }}, {{ weather.weather_colors[1] }});
            color: #fff;
            padding: 20px;
            width: 500px;
        }
        .container {
            background-color: rgba(0, 0, 0, 0.3);
            border-radius: 15px;
            padding: 20px;
        }
        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 2px solid rgba(255, 255, 255, 0.5);
            padding-bottom: 10px;
            margin-bottom: 10px;
        }
        .header h1 {
            font-size: 28px;
            margin: 0;
        }
        .header .updated {
            font-size: 14px;
            opacity: 0.8;
        }
        .main-weather {
            display: flex;
            align-items: center;
            justify-content: space-around;
            text-align: center;
            margin: 20px 0;
        }
        .main-weather .temp {
            font-size: 72px;
            font-weight: bold;
        }
        .main-weather .condition {
            font-size: 24px;
        }
        .details {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 15px;
            font-size: 16px;
        }
        .details div {
            background-color: rgba(0, 0, 0, 0.2);
            padding: 10px;
            border-radius: 8px;
        }
        .tips {
            margin-top: 20px;
            border-top: 2px solid rgba(255, 255, 255, 0.5);
            padding-top: 10px;
        }
        .tips h2 {
            font-size: 20px;
            margin-bottom: 10px;
        }
        .tips p {
            font-size: 16px;
            margin: 5px 0;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{{ location.name }}</h1>
            <span class="updated">更新于: {{ weather.updated.split(' ')[1] }}</span>
        </div>
        <div class="main-weather">
            <img src="{{ weather.weather_icon }}" alt="weather_icon" width="80" height="80">
            <div>
                <div class="temp">{{ weather.temperature }}°</div>
                <div class="condition">{{ weather.condition }}</div>
            </div>
        </div>
        <div class="details">
            <div><strong>湿度:</strong> {{ weather.humidity }}%</div>
            <div><strong>风力:</strong> {{ weather.wind_direction }} {{ weather.wind_power }}级</div>
            <div><strong>空气质量:</strong> {{ air.quality }} (AQI: {{ air.aqi }})</div>
            <div><strong>日出/日落:</strong> {{ sunrise.sunrise_desc }} / {{ sunrise.sunset_desc }}</div>
        </div>
        <div class="tips">
            <h2>生活小贴士</h2>
            <p><strong>穿衣:</strong> {{ clothes.description }}</p>
            <p><strong>运动:</strong> {{ sports.description }}</p>
        </div>
    </div>
</body>
</html>
"""

@register("weather", "Assistant", "一个简单的天气查询插件", "1.0.0")
class WeatherPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)

    @filter.command("天气")
    async def get_weather(self, event: AstrMessageEvent, city: str = None):
        """
        获取指定城市的天气信息并以图片形式发送。
        """
        # [新增] 检查用户是否输入了城市
        if not city:
            yield event.plain_result("请输入要查询的城市，例如：/天气 北京")
            return

        api_url = f"https://60s.viki.moe/v2/weather?query={city}"
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(api_url, timeout=10)
                response.raise_for_status()
                data = response.json()

            if data.get("code") != 200:
                yield event.plain_result(f"查询失败: {data.get('message', '未知错误')}")
                return

            weather_data = data["data"]

            # 从生活指数中找到穿衣和运动建议
            life_indices = weather_data.get("life_indices", [])
            clothes_tip = next((item for item in life_indices if item['key'] == 'clothes'), {"description": "暂无"})
            sports_tip = next((item for item in life_indices if item['key'] == 'sports'), {"description": "暂无"})

            # 准备渲染模板所需的数据
            render_payload = {
                "location": weather_data["location"],
                "weather": weather_data["weather"],
                "air": weather_data["air_quality"],
                "sunrise": weather_data["sunrise"],
                "clothes": clothes_tip,
                "sports": sports_tip
            }

            # 调用html_render方法生成图片并获取URL
            image_url = await self.html_render(WEATHER_TEMPLATE, render_payload)
            yield event.image_result(image_url)

        except httpx.RequestError as e:
            logger.error(f"请求天气API时出错: {e}")
            yield event.plain_result(f"网络错误，无法连接到天气服务。")
        except KeyError as e:
            logger.error(f"解析天气数据时缺少键: {e}")
            yield event.plain_result(f"无法解析'{city}'的天气数据，请确保城市名称正确。")
        except Exception as e:
            logger.error(f"处理天气查询时发生未知错误: {e}")
            yield event.plain_result(f"查询天气时发生未知错误。")