import json
import functools
import requests
from django.conf import settings
from django.shortcuts import render, redirect, HttpResponse
from django.http import JsonResponse
from app01 import models
# 沙箱环境地质：https://mp.weixin.qq.com/debug/cgi-bin/sandbox?t=sandbox/login
def index(request):
    # 测试用，查看是否有 微信ID
    obj = models.UserInfo.objects.get(id=1)
    return render(request,'index.html',{'obj':obj})


def auth(func):
    @functools.wraps(func)
    def inner(request, *args, **kwargs):
        user_info = request.session.get('user_info')
        if not user_info:
            return redirect('/login/')
        return func(request, *args, **kwargs)

    return inner


def login(request):
    """
    用户登录
    :param request: 
    :return: 
    """
    # models.UserInfo.objects.create(username='luffy',password=123)

    if request.method == "POST":
        user = request.POST.get('user')
        pwd = request.POST.get('pwd')
        obj = models.UserInfo.objects.filter(username=user, password=pwd).first()
        if obj:
            request.session['user_info'] = {'id': obj.id, 'name': obj.username, 'uid': obj.uid}
            return redirect('/bind/')
    else:
        return render(request, 'login.html')


@auth
def bind(request):
    """
    用户登录后，关注公众号，并绑定个人微信（用于以后消息推送）
    :param request: 
    :return: 
    """
    return render(request, 'bind.html')


@auth
def bind_qcode(request):
    """
    生成二维码，让用户扫码（向微信发送请求，获取用户信息。然后微信回调 url:http://47.93.4.198/callback/, 在callback中获取用户唯一标识）
    :param request: 
    :return: 
    """
    ret = {'code': 1000}
    try:
        access_url = "https://open.weixin.qq.com/connect/oauth2/authorize?appid={appid}&redirect_uri={redirect_uri}&response_type=code&scope=snsapi_userinfo&state={state}#wechat_redirect"
        access_url = access_url.format(
            appid=settings.WECHAT_CONFIG["app_id"],  # settings 里配置的 appID
            redirect_uri=settings.WECHAT_CONFIG["redirect_uri"],  # settings 里配置，微信向地址发送请求，把微信号的字符串给我。'http://47.93.4.198/callback/',
            state=request.session['user_info']['uid']  # 为当前用户生成MD5值
        )
        ret['data'] = access_url
    except Exception as e:
        ret['code'] = 1001
        ret['msg'] = str(e)

    return JsonResponse(ret)


def callback(request):
    """
    用户在手机微信上扫码后，微信自动调用该方法。
    用于获取扫码用户的唯一ID，以后用于给他推送消息。
    :param request: 
    :return: 
    """
    code = request.GET.get("code")

    # 用户md5值
    state = request.GET.get("state")

    # 去微信获取该用户微信号字符串(用户唯一，用于给用户发送消息)
    res = requests.get(
        url="https://api.weixin.qq.com/sns/oauth2/access_token",  # 不可改
        params={
            "appid": 'wx89085e915d351cae',
            "secret": '64f87abfc664f1d4f11d0ac98b24c42d',
            "code": code,
            "grant_type": 'authorization_code',
        }
    ).json()
    # 获取的到openid表示用户授权成功
    openid = res.get("openid")
    if openid:
        models.UserInfo.objects.filter(uid=state).update(wx_id=openid)
        response = "<h1>授权成功 %s </h1>" % openid
    else:
        response = "<h1>用户扫码之后，手机上的提示</h1>"
    return HttpResponse(response)


def sendmsg(request):
    """发送消息"""
    def get_access_token():
        """
        获取微信全局接口的凭证(默认有效期俩个小时), 获取token
        如果不每天请求次数过多, 通过设置缓存即可
        """
        result = requests.get(
            url="https://api.weixin.qq.com/cgi-bin/token",  # 获取微信的token。 不可更改
            params={  # 不可更改
                "grant_type": "client_credential",
                "appid": settings.WECHAT_CONFIG['app_id'],
                "secret": settings.WECHAT_CONFIG['appsecret'],
            }
        ).json()
        if result.get("access_token"):
            access_token = result.get('access_token')
        else:
            access_token = None
        return access_token

    access_token = get_access_token()

    openid = models.UserInfo.objects.get(id=1).wx_id

    def send_custom_msg():
        """发送自定义文本消息"""
        body = {
            "touser": openid,
            "msgtype": "text",
            "text": {
                "content": '不错哦~~'
            }
        }
        response = requests.post(
            url="https://api.weixin.qq.com/cgi-bin/message/custom/send",  # 微信发送文本消息的接口。不可更改
            params={
                'access_token': access_token
            },
            data=bytes(json.dumps(body, ensure_ascii=False), encoding='utf-8')  # ensure_ascii 中文
        )
        # 这里可根据回执code进行判定是否发送成功(也可以根据code根据错误信息)
        result = response.json()
        return result

    def send_template_msg():
        """
        发送模版消息。 需要在微信设置 模板消息接口
        """
        res = requests.post(
            url="https://api.weixin.qq.com/cgi-bin/message/template/send",  # 微信发送模板消息的接口。不可更改
            params={
                'access_token': access_token
            },
            json={
                "touser": openid,
                "template_id": 'm277nyW45IIkxUg-p6zd9N9wCmGqVGCA-HK8uCD-xUs',  # 微信上的模板ID，
                "data": {
                    "first": {  # 微信接口里的占位符  {{first.DATA}}  是个 {{keyworld.DATA}}
                        "value": "邢溢",
                        "color": "#173177"
                    },
                    "keyworld": {
                        "value": "笨蛋",
                        "color": "#173177"
                    },
                }
            }
        )
        result = res.json()
        return result

    result = send_template_msg()

    if result.get('errcode') == 0:
        return HttpResponse('发送成功')
    return HttpResponse('发送失败')
