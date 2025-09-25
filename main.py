import httpx
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger

# 最终版模板
WEATHER_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>天气信息</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@400;500;700&display=swap');
        body {
            font-family: 'Noto Sans SC', sans-serif;
            background-color: #525f75;
            color: #f8f9fa;
            padding: 20px;
            width: 500px;
            box-sizing: border-box;
            margin: 0;
        }
        .container {
            background-color: #3e4a5d;
            border-radius: 12px;
            padding: 25px;
        }
        .header {
            display: flex;
            justify-content: space-between;
            align-items: baseline;
            border-bottom: 1px solid #525f75;
            padding-bottom: 15px;
            margin-bottom: 15px;
        }
        .header h1 {
            font-size: 26px;
            font-weight: 700;
            margin: 0;
        }
        .header .updated {
            font-size: 13px;
            color: #adb5bd;
        }
        .main-weather {
            display: flex;
            align-items: center;
            justify-content: flex-start;
            gap: 20px;
            text-align: left;
            margin: 25px 5px;
        }
        .main-weather .temp {
            font-size: 68px;
            font-weight: 700;
            line-height: 1;
        }
        .main-weather .condition {
            font-size: 22px;
            font-weight: 500;
        }
        .main-weather img {
            width: 70px;
            height: 70px;
        }
        .details {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 12px;
            font-size: 14px;
        }
        .details div {
            background-color: #4a5568;
            padding: 12px;
            border-radius: 8px;
        }
        .tips {
            margin-top: 20px;
            border-top: 1px solid #525f75;
            padding-top: 15px;
        }
        .tips h2 {
            font-size: 18px;
            margin-bottom: 12px;
            font-weight: 700;
        }
        .tips p {
            font-size: 14px;
            margin: 8px 0;
            line-height: 1.6;
        }
        .tips strong {
            color: #ced4da;
            font-weight: 500;
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
            <img src="{{ weather.weather_icon }}" alt="weather_icon">
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
            {% for tip in life_tips %}
            <p><strong>{{ tip.name }}:</strong> {{ tip.level }}。{{ tip.description }}</p>
            {% endfor %}
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
    # [修正] 使用唯一正确的函数签名，以防止 TypeError
    async def get_weather(self, event: AstrMessageEvent, args: tuple = ()):
        """
        获取指定城市的天气信息并以图片形式发送。
        """
        if not args:
            yield event.plain_result("请输入要查询的城市，例如：!天气 北京")
            return

        city = " ".join(args)

        api_url = f"https://60s.viki.moe/v2/weather?query={city}"
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(api_url, timeout=10)
                response.raise_for_status()
                data = response.json()

            # [修正] 采用更严格的校验，防止 'KeyError'
            weather_data = data.get("data")
            if not weather_data or "location" not in weather_data:
                yield event.plain_result(f"查询失败: {data.get('message', '无法获取到该城市的天气数据')}")
                return

            desired_keys = ['clothes', 'sports', 'cold', 'ultraviolet', 'carwash', 'tourism']
            all_indices = weather_data.get("life_indices", [])
            
            display_tips = [
                tip for tip in all_indices if tip['key'] in desired_keys
            ]

            render_payload = {
                "location": weather_data["location"],
                "weather": weather_data["weather"],
                "air": weather_data["air_quality"],
                "sunrise": weather_data["sunrise"],
                "life_tips": display_tips
            }
            
            render_options = {
                "device_scale_factor": 2
            }

            image_url = await self.html_render(WEATHER_TEMPLATE, render_payload, options=render_options)
            yield event.image_result(image_url)

        except httpx.RequestError as e:
            logger.error(f"请求天气API时出错: {e}")
            yield event.plain_result(f"网络错误，无法连接到天气服务。")
        except KeyError as e:
            # 这里的 KeyError 作为一个备用安全网，理论上不应该再被触发
            logger.error(f"解析天气数据时缺少键: {e}")
            yield event.plain_result(f"无法解析'{city}'的天气数据，请确保城市名称正确。")
        except Exception as e:
            logger.error(f"处理天气查询时发生未知错误: {e}")
            yield event.plain_result(f"查询天气时发生未知错误。")